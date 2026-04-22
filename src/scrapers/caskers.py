"""Caskers scraper.

Uses the Magento 2 search autocomplete API to find in-stock bourbon
listings. No authentication required.
"""

from __future__ import annotations

import re

import httpx
import structlog

from src.models import Listing
from src.scrapers.base import AbstractScraper

logger = structlog.get_logger()

AUTOCOMPLETE_URL = "https://www.caskers.com/searchautocomplete/ajax/suggest/"

# Search terms targeting allocated / rare bourbons
SEARCH_TERMS = [
    "Weller",
    "Blanton's",
    "Pappy",
    "E.H. Taylor",
    "Stagg",
    "Eagle Rare",
    "Buffalo Trace",
    "allocated",
    "limited",
]

# Try data-price-amount first, then fall back to $XX.XX in text
_DATA_PRICE_RE = re.compile(r'data-price-amount="([\d.]+)"')
_TEXT_PRICE_RE = re.compile(r"\$\s*([\d,]+\.?\d*)")


def _parse_price(raw: str | None) -> float | None:
    """Extract a float price from Magento HTML price markup."""
    if not raw:
        return None
    # data-price-amount="56.99" is the most reliable
    m = _DATA_PRICE_RE.search(raw)
    if not m:
        m = _TEXT_PRICE_RE.search(raw)
    if not m:
        return None
    try:
        return float(m.group(1).replace(",", ""))
    except (ValueError, TypeError):
        return None


def _parse_result(item: dict) -> Listing | None:
    """Convert a single autocomplete result dict into a Listing.

    Returns None if the item is out of stock or missing required fields.
    """
    # stockStatus 2 = in stock
    if item.get("stockStatus") != 2:
        return None

    sku = item.get("sku")
    title = item.get("name")
    url = item.get("url")
    if not sku or not title or not url:
        return None

    return Listing(
        source="caskers",
        external_id=str(sku),
        title=title,
        url=url,
        price=_parse_price(item.get("price")),
        image_url=item.get("imageUrl"),
    )


class CaskersScraper(AbstractScraper):
    @property
    def source_name(self) -> str:
        return "caskers"

    def scrape(self) -> list[Listing]:
        seen_skus: set[str] = set()
        listings: list[Listing] = []
        client = httpx.Client(
            headers={
                "Accept": "application/json",
                "User-Agent": "Mozilla/5.0",
            },
            timeout=30,
        )

        try:
            for term in SEARCH_TERMS:
                results = self._search(client, term)
                for item in results:
                    listing = _parse_result(item)
                    if listing is None:
                        continue
                    if listing.external_id in seen_skus:
                        continue
                    seen_skus.add(listing.external_id)
                    listings.append(listing)
        except httpx.HTTPError as e:
            logger.error("caskers.http_error", error=str(e))
        finally:
            client.close()

        logger.info("caskers.scrape_complete", count=len(listings))
        return listings

    def _search(self, client: httpx.Client, query: str) -> list[dict]:
        """Hit the autocomplete endpoint for a single search term."""
        logger.info("caskers.searching", query=query)
        resp = client.get(AUTOCOMPLETE_URL, params={"q": query})
        resp.raise_for_status()
        data = resp.json()

        # Response shape: {"indexes": [{"items": [...]}], ...}
        if isinstance(data, dict):
            indexes = data.get("indexes", [])
            if indexes and isinstance(indexes, list):
                return indexes[0].get("items", [])
        return []
