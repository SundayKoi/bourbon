"""Seelbachs scraper.

Uses the public Shopify JSON API to fetch bourbon products from Seelbachs.
No authentication required. Monitors new arrivals and last-chance collections.
Run --seed first to populate the DB without sending notifications.
"""

from __future__ import annotations

import httpx
import structlog

from src.models import Listing
from src.scrapers.base import AbstractScraper

logger = structlog.get_logger()

BASE_URL = "https://www.seelbachs.com"

COLLECTIONS = {
    "new-products": f"{BASE_URL}/collections/new-products/products.json",
    "last-chance": f"{BASE_URL}/collections/last-chance/products.json",
}

WHISKEY_TAGS = {"sub_category:bourbon", "sub_category:rye", "category:whiskey"}
WHISKEY_PRODUCT_TYPES = {"bourbon", "rye", "whiskey", "whisky"}

MAX_PAGES = 10  # safety limit


def _is_whiskey(product: dict) -> bool:
    """Check if a product is bourbon/whiskey based on tags or product_type."""
    tags = [t.strip().lower() for t in product.get("tags", [])]
    if any(tag in WHISKEY_TAGS for tag in tags):
        return True

    product_type = (product.get("product_type") or "").lower()
    if product_type in WHISKEY_PRODUCT_TYPES:
        return True

    return False


def _is_available(product: dict) -> bool:
    """Check if at least one variant is available."""
    for variant in product.get("variants", []):
        if variant.get("available"):
            return True
    return False


def _parse_product(product: dict) -> Listing | None:
    """Parse a Shopify product JSON into a Listing."""
    product_id = product.get("id")
    title = product.get("title", "")
    handle = product.get("handle", "")

    if not product_id or not title or not handle:
        return None

    if not _is_whiskey(product):
        return None

    if not _is_available(product):
        return None

    # Price from first variant
    price: float | None = None
    variants = product.get("variants", [])
    if variants:
        raw_price = variants[0].get("price")
        if raw_price is not None:
            try:
                price = float(raw_price)
            except (ValueError, TypeError):
                pass

    # Image from first image entry
    image_url: str | None = None
    images = product.get("images", [])
    if images:
        image_url = images[0].get("src")

    url = f"{BASE_URL}/products/{handle}"

    return Listing(
        source="seelbachs",
        external_id=str(product_id),
        title=title,
        url=url,
        price=price,
        image_url=image_url,
    )


class SeelbachsScraper(AbstractScraper):
    @property
    def source_name(self) -> str:
        return "seelbachs"

    def scrape(self) -> list[Listing]:
        listings: list[Listing] = []
        seen_ids: set[str] = set()

        client = httpx.Client(
            headers={"Accept": "application/json"},
            timeout=30,
        )

        try:
            for collection, url in COLLECTIONS.items():
                products = self._fetch_collection(client, collection, url)
                for product in products:
                    listing = _parse_product(product)
                    if listing and listing.external_id not in seen_ids:
                        seen_ids.add(listing.external_id)
                        listings.append(listing)

        except httpx.HTTPError as e:
            logger.error("seelbachs.http_error", error=str(e))
        finally:
            client.close()

        logger.info("seelbachs.scrape_complete", count=len(listings))
        return listings

    def _fetch_collection(
        self, client: httpx.Client, collection: str, base_url: str
    ) -> list[dict]:
        """Fetch all pages of a Shopify collection."""
        products: list[dict] = []
        page = 1

        while page <= MAX_PAGES:
            url = f"{base_url}?limit=250&page={page}"
            logger.info(
                "seelbachs.fetching_page", collection=collection, page=page
            )

            resp = client.get(url)
            resp.raise_for_status()
            data = resp.json()

            page_products = data.get("products", [])
            if not page_products:
                break

            products.extend(page_products)
            page += 1

        logger.info(
            "seelbachs.collection_fetched",
            collection=collection,
            count=len(products),
        )
        return products
