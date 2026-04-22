"""Whisky Auctioneer scraper.

Uses curl_cffi to bypass Fastly bot protection with browser TLS fingerprinting.
Searches for bourbon lots via the Drupal Views AJAX endpoint.

The site has a 10-second crawl-delay in robots.txt, so we respect that.
"""

from __future__ import annotations

import json
import re
import time

import structlog
from bs4 import BeautifulSoup
from curl_cffi import requests as cffi_requests

from src.models import Listing
from src.scrapers.base import AbstractScraper

logger = structlog.get_logger()

BASE_URL = "https://whiskyauctioneer.com"
VIEWS_AJAX_URL = f"{BASE_URL}/views/ajax"
CRAWL_DELAY = 10  # per robots.txt


class WhiskyAuctioneerScraper(AbstractScraper):
    @property
    def source_name(self) -> str:
        return "whisky_auctioneer"

    def scrape(self) -> list[Listing]:
        listings: list[Listing] = []
        session = cffi_requests.Session(impersonate="chrome")

        try:
            # First, get the active auction ID from the main page
            auction_id = self._get_active_auction_id(session)
            if not auction_id:
                logger.warning("whisky_auctioneer.no_active_auction")
                return []

            logger.info("whisky_auctioneer.active_auction", auction_id=auction_id)

            # Search for bourbon lots via Views AJAX
            page = 0
            max_pages = 5  # safety limit

            while page < max_pages:
                time.sleep(CRAWL_DELAY)
                new_listings = self._fetch_lots_page(session, auction_id, page)

                if not new_listings:
                    break

                listings.extend(new_listings)
                page += 1

        except Exception as e:
            logger.error("whisky_auctioneer.error", error=str(e))
        finally:
            session.close()

        logger.info("whisky_auctioneer.scrape_complete", count=len(listings))
        return listings

    def _get_active_auction_id(self, session: cffi_requests.Session) -> str | None:
        """Get the current active auction ID from the site."""
        try:
            resp = session.get(f"{BASE_URL}/whisky-auctions", timeout=30)
            resp.raise_for_status()

            # Look for auction ID in Drupal settings JSON
            match = re.search(
                r'"activeAuctions"\s*:\s*\{["\s]*(\d+)', resp.text
            )
            if match:
                return match.group(1)

            # Fallback: look for auction links
            soup = BeautifulSoup(resp.text, "lxml")
            for link in soup.find_all("a", href=re.compile(r"/whisky-auctions/.*auction/lots")):
                return link["href"]

        except Exception as e:
            logger.error("whisky_auctioneer.auction_id_error", error=str(e))
        return None

    def _fetch_lots_page(
        self, session: cffi_requests.Session, auction_id: str, page: int
    ) -> list[Listing]:
        """Fetch a page of bourbon lots via Views AJAX."""
        logger.info("whisky_auctioneer.fetching_page", page=page)

        form_data = {
            "view_name": "lots_index",
            "view_display_id": "lots_page",
            "view_args": auction_id,
            "page": str(page),
            "search_keyword": "bourbon",
        }

        try:
            resp = session.post(
                VIEWS_AJAX_URL,
                data=form_data,
                headers={
                    "Accept": "application/json, text/javascript, */*; q=0.01",
                    "X-Requested-With": "XMLHttpRequest",
                    "Content-Type": "application/x-www-form-urlencoded",
                },
                timeout=30,
            )

            if resp.status_code == 406:
                logger.warning("whisky_auctioneer.bot_blocked", page=page)
                return []

            resp.raise_for_status()
            return self._parse_ajax_response(resp.json())

        except Exception as e:
            logger.error("whisky_auctioneer.fetch_error", page=page, error=str(e))
            return []

    def _parse_ajax_response(self, ajax_data: list) -> list[Listing]:
        """Parse the Drupal Views AJAX response to extract lot cards."""
        listings: list[Listing] = []

        # Find the insert command with lot HTML
        html_content = ""
        for cmd in ajax_data:
            if isinstance(cmd, dict) and cmd.get("command") == "insert":
                data = cmd.get("data", "")
                if "lot-teaser" in data or "views-row" in data:
                    html_content = data
                    break

        if not html_content:
            return []

        soup = BeautifulSoup(html_content, "lxml")
        lot_cards = soup.select("div.lot-teaser")

        for card in lot_cards:
            listing = self._parse_lot_card(card)
            if listing:
                listings.append(listing)

        return listings

    def _parse_lot_card(self, card) -> Listing | None:
        """Parse a single lot card element into a Listing."""
        # Title
        title_el = card.select_one("h3.teaser-title a")
        if not title_el:
            return None
        title = title_el.get_text(strip=True)

        # URL
        link_el = card.select_one("a.stretched-link") or title_el
        href = link_el.get("href", "")
        url = href if href.startswith("http") else f"{BASE_URL}{href}"

        # SKU / lot number for external_id
        sku_el = card.select_one(".sku")
        sku = sku_el.get_text(strip=True).strip("#") if sku_el else ""

        if not sku:
            match = re.search(r"/whisky-lot/(\d+)/", url)
            sku = match.group(1) if match else url.split("/")[-1]

        # Bid data from data attributes
        bid_el = card.select_one("div.bid-app-main")
        price = None
        if bid_el:
            datalayer = bid_el.get("data-datalayer", "")
            if datalayer:
                try:
                    dl = json.loads(datalayer)
                    value = dl.get("value")
                    if value:
                        # Value is in pence, convert to GBP
                        price = float(value) / 100
                except (json.JSONDecodeError, TypeError):
                    pass

        # Image
        img_el = card.select_one(".teaser-image img")
        image_url = img_el.get("src", "") if img_el else None

        return Listing(
            source="whisky_auctioneer",
            external_id=sku,
            title=title,
            url=url,
            price=price,
            currency="GBP",
            image_url=image_url or None,
        )
