"""BreakingBourbon scraper.

Scrapes press releases (Webflow CMS collection) for bourbon news and new releases.
The press releases page has clean structure with .w-dyn-item elements and pagination.
"""

from __future__ import annotations

import hashlib
import re
from datetime import datetime, timezone

import httpx
import structlog
from bs4 import BeautifulSoup

from src.models import Listing
from src.scrapers.base import AbstractScraper

logger = structlog.get_logger()

BASE_URL = "https://www.breakingbourbon.com"
PRESS_RELEASES_URL = f"{BASE_URL}/bourbon-rye-whiskey-press-releases"
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)


class BreakingBourbonScraper(AbstractScraper):
    @property
    def source_name(self) -> str:
        return "breaking_bourbon"

    def scrape(self) -> list[Listing]:
        listings: list[Listing] = []
        client = httpx.Client(
            headers={"User-Agent": USER_AGENT},
            follow_redirects=True,
            timeout=30,
        )

        try:
            page = 1
            max_pages = 5  # safety limit
            while page <= max_pages:
                url = PRESS_RELEASES_URL
                if page > 1:
                    url = f"{PRESS_RELEASES_URL}?7f5918a3_page={page}"

                logger.info("breaking_bourbon.fetching_page", page=page)
                resp = client.get(url)
                resp.raise_for_status()

                soup = BeautifulSoup(resp.text, "lxml")
                items = soup.select("div.w-dyn-item")

                if not items:
                    break

                for item in items:
                    listing = self._parse_item(item)
                    if listing:
                        listings.append(listing)

                # Check for next page
                next_link = soup.select_one("a.w-pagination-next")
                if not next_link:
                    break
                page += 1

                # Only scrape first page on routine runs (recent releases)
                # Full pagination is for initial backfill
                if page > 2:
                    break

        except httpx.HTTPError as e:
            logger.error("breaking_bourbon.http_error", error=str(e))
        finally:
            client.close()

        logger.info("breaking_bourbon.scrape_complete", count=len(listings))
        return listings

    def _parse_item(self, item) -> Listing | None:
        """Parse a single .w-dyn-item element into a Listing."""
        # Title — site uses div.text-block-59 inside a.link-block-50
        title_el = item.select_one("div.text-block-59")
        if not title_el:
            return None
        title = title_el.get_text(strip=True)

        # Link
        link_el = item.select_one("a.link-block-50")
        if not link_el:
            link_el = item.select_one(
                'a[href*="/bourbon-whiskey-press-releases/"]'
            )
        url = ""
        if link_el and link_el.get("href"):
            href = link_el["href"]
            url = href if href.startswith("http") else f"{BASE_URL}{href}"

        if not url:
            return None

        # Date — site uses div.text-block-60
        date_el = item.select_one("div.text-block-60")
        date_text = date_el.get_text(strip=True) if date_el else ""

        # Generate a stable external ID from the URL slug
        slug = url.rstrip("/").split("/")[-1]
        external_id = slug or hashlib.md5(url.encode()).hexdigest()

        return Listing(
            source="breaking_bourbon",
            external_id=external_id,
            title=title,
            url=url,
        )
