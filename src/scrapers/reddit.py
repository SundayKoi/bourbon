"""Reddit scraper for r/bourbon and r/whiskey.

Uses Reddit's public JSON API (append .json to any listing URL).
No authentication required.
"""

from __future__ import annotations

import time
from datetime import datetime, timezone

import httpx
import structlog

from src.models import Listing
from src.scrapers.base import AbstractScraper

logger = structlog.get_logger()

USER_AGENT = "bourbon-alerts/0.1 (personal notification bot)"

# Keywords that suggest a post is about a drop, lottery, or availability
SALE_KEYWORDS = [
    "auction", "sale", "drop", "release", "lottery", "allocated",
    "found", "pickup", "store", "shelf", "available", "raffle",
    "retail", "msrp", "limited", "special release",
    "spotted", "scored", "grab", "haul", "got lucky",
    "new arrival", "in stock", "just dropped",
]

# Posts matching these keywords are skipped even if SALE_KEYWORDS match
EXCLUDE_KEYWORDS = [
    "review", "reviewed", "tasting notes", "nose:", "palate:", "finish:",
    "rating:", "/10", "/100", "my rating", "bottle kill",
]


class RedditScraper(AbstractScraper):
    def __init__(self, subreddits: list[str] | None = None) -> None:
        self.subreddits = subreddits or ["bourbon", "whiskey"]

    @property
    def source_name(self) -> str:
        return "reddit"

    def scrape(self) -> list[Listing]:
        listings: list[Listing] = []
        client = httpx.Client(
            headers={"User-Agent": USER_AGENT},
            follow_redirects=True,
            timeout=30,
        )

        try:
            for subreddit in self.subreddits:
                posts = self._scrape_subreddit(client, subreddit)
                listings.extend(posts)
                # Be polite between subreddits
                if len(self.subreddits) > 1:
                    time.sleep(2)
        except httpx.HTTPError as e:
            logger.error("reddit.http_error", error=str(e))
        finally:
            client.close()

        logger.info("reddit.scrape_complete", count=len(listings))
        return listings

    def _scrape_subreddit(self, client: httpx.Client, subreddit: str) -> list[Listing]:
        """Fetch new posts from a subreddit and filter for sale/auction relevance."""
        url = f"https://www.reddit.com/r/{subreddit}/new.json?limit=50"
        logger.info("reddit.fetching", subreddit=subreddit)

        resp = client.get(url)
        resp.raise_for_status()
        data = resp.json()

        listings: list[Listing] = []
        children = data.get("data", {}).get("children", [])

        for child in children:
            post = child.get("data", {})
            listing = self._parse_post(post, subreddit)
            if listing:
                listings.append(listing)

        logger.info("reddit.subreddit_done", subreddit=subreddit, count=len(listings))
        return listings

    def _parse_post(self, post: dict, subreddit: str) -> Listing | None:
        """Parse a Reddit post into a Listing if it's sale/auction related."""
        post_id = post.get("id", "")
        title = post.get("title", "")
        permalink = post.get("permalink", "")

        if not post_id or not title:
            return None

        # Filter: only include posts about drops/lotteries/availability, not reviews
        title_lower = title.lower()
        selftext_lower = post.get("selftext", "").lower()
        combined = title_lower + " " + selftext_lower

        if any(kw in combined for kw in EXCLUDE_KEYWORDS):
            return None

        if not any(kw in combined for kw in SALE_KEYWORDS):
            return None

        url = f"https://www.reddit.com{permalink}" if permalink else ""
        if not url:
            return None

        created_utc = post.get("created_utc", 0)
        discovered = datetime.fromtimestamp(created_utc, tz=timezone.utc) if created_utc else None

        return Listing(
            source="reddit",
            external_id=post_id,
            title=f"r/{subreddit}: {title}",
            url=url,
            **({"discovered_at": discovered} if discovered else {}),
        )
