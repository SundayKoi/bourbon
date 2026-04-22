"""Virginia ABC lottery scraper.

Uses curl_cffi to bypass Cloudflare bot protection with browser TLS fingerprinting.
Fetches the JSON API at abc.virginia.gov/lotto/api/event/getEvents for active
lottery events, and falls back to scraping the HTML lottery page.
"""

from __future__ import annotations

from datetime import datetime, timezone

import structlog
from bs4 import BeautifulSoup
from curl_cffi import requests as cffi_requests

from src.models import Listing
from src.scrapers.base import AbstractScraper

logger = structlog.get_logger()

LOTTERY_API_URL = "https://www.abc.virginia.gov/lotto/api/event/getEvents"
LOTTERY_PAGE_URL = "https://www.abc.virginia.gov/products/limited-availability/lottery"
PRODUCT_URL_BASE = "https://www.abc.virginia.gov/products/bourbon"


class VirginiaABCScraper(AbstractScraper):
    @property
    def source_name(self) -> str:
        return "virginia_abc"

    def scrape(self) -> list[Listing]:
        listings: list[Listing] = []
        session = cffi_requests.Session(impersonate="chrome")

        try:
            # Try the JSON API first
            api_listings = self._fetch_api_events(session)
            if api_listings:
                listings.extend(api_listings)
            else:
                # Fall back to scraping the HTML lottery page
                logger.info("virginia_abc.falling_back_to_html")
                html_listings = self._scrape_lottery_page(session)
                listings.extend(html_listings)

        except Exception as e:
            logger.error("virginia_abc.error", error=str(e))
        finally:
            session.close()

        logger.info("virginia_abc.scrape_complete", count=len(listings))
        return listings

    def _fetch_api_events(self, session: cffi_requests.Session) -> list[Listing]:
        """Try to fetch lottery events from the JSON API."""
        listings: list[Listing] = []

        for event_type in (2, 3):  # 2=lottery, 3=FCFS
            logger.info("virginia_abc.fetching_api", event_type=event_type)
            try:
                resp = session.get(
                    LOTTERY_API_URL,
                    params={"eventTypeId": event_type},
                    timeout=30,
                )
                if resp.status_code == 403:
                    logger.warning("virginia_abc.api_blocked", event_type=event_type)
                    return []  # signal to fall back to HTML

                resp.raise_for_status()
                data = resp.json()

                for event_id, event in data.items():
                    products = event.get("products", [])
                    event_name = event.get("eventName", f"Event {event_id}")

                    ends_at = None
                    end_ms = event.get("bidEndDatetime")
                    if end_ms:
                        try:
                            ends_at = datetime.fromtimestamp(end_ms / 1000, tz=timezone.utc)
                        except (ValueError, OSError):
                            pass

                    for product in products:
                        listing = self._parse_api_product(product, event_id, ends_at)
                        if listing:
                            listings.append(listing)

            except Exception as e:
                logger.error("virginia_abc.api_error", event_type=event_type, error=str(e))
                return []  # signal to fall back to HTML

        return listings

    def _parse_api_product(
        self,
        product: dict,
        event_id: str,
        ends_at: datetime | None,
    ) -> Listing | None:
        """Parse a lottery product from the API response."""
        product_id = product.get("lotteryEventProductId", "")
        product_name = product.get("productName", "")

        if not product_name or not product_id:
            return None

        price = product.get("retailBottlePrice")
        qty = product.get("availableQty", 0)
        size = product.get("bottleSize", "")

        title = f"VA Lottery: {product_name}"
        if size:
            title += f" ({size})"
        if qty:
            title += f" - {qty} available"

        slug = product_name.lower().replace(" ", "-").replace("'", "")
        url = f"{PRODUCT_URL_BASE}/{slug}?productSize=0"

        return Listing(
            source="virginia_abc",
            external_id=f"va-{event_id}-{product_id}",
            title=title,
            url=url,
            price=float(price) if price is not None else None,
            ends_at=ends_at,
        )

    def _scrape_lottery_page(self, session: cffi_requests.Session) -> list[Listing]:
        """Fallback: scrape the HTML lottery info page."""
        listings: list[Listing] = []

        try:
            resp = session.get(LOTTERY_PAGE_URL, timeout=30)
            if resp.status_code == 403:
                logger.warning("virginia_abc.html_also_blocked")
                return []
            resp.raise_for_status()
        except Exception as e:
            logger.error("virginia_abc.html_error", error=str(e))
            return []

        soup = BeautifulSoup(resp.text, "lxml")

        # Find "Current Lottery Distributions" section
        for h2 in soup.find_all("h2"):
            if "current lottery" in h2.get_text(strip=True).lower():
                # Get the parent card's content body
                card = h2.find_parent("div", class_="abc-card")
                if not card:
                    continue

                content = card.select_one(".content-body")
                if not content:
                    continue

                for li in content.find_all("li"):
                    listing = self._parse_html_listing(li)
                    if listing:
                        listings.append(listing)
                break

        return listings

    def _parse_html_listing(self, li) -> Listing | None:
        """Parse a <li> element from the lottery page into a Listing."""
        text = li.get_text(strip=True)
        if not text:
            return None

        # Extract link if present
        link = li.find("a")
        url = ""
        title = text
        if link:
            url = link.get("href", "")
            if url and not url.startswith("http"):
                url = f"https://www.abc.virginia.gov{url}"
            title = link.get_text(strip=True)

        if not url:
            url = LOTTERY_PAGE_URL

        # Try to extract price from text like "($2,999.99)"
        import re
        price = None
        price_match = re.search(r'\$([0-9,]+\.?\d*)', text)
        if price_match:
            price = float(price_match.group(1).replace(",", ""))

        # Generate stable ID from title
        slug = re.sub(r'[^a-z0-9]+', '-', title.lower()).strip('-')
        external_id = f"va-html-{slug}"

        return Listing(
            source="virginia_abc",
            external_id=external_id,
            title=f"VA Lottery: {title}",
            url=url,
            price=price,
        )
