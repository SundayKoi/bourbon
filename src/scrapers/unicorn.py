"""Unicorn Auctions scraper.

Uses the public GraphQL API at graphql.beta.unicornauctions.com to fetch
live/upcoming auction lots. No authentication required for public queries.
"""

from __future__ import annotations

from datetime import datetime, timezone

import httpx
import structlog

from src.models import Listing
from src.scrapers.base import AbstractScraper

logger = structlog.get_logger()

SITE_URL = "https://www.unicornauctions.com"
GRAPHQL_URL = "https://graphql.beta.unicornauctions.com/graphql"

# Query to get live and upcoming auctions
AUCTIONS_QUERY = """
query {
  liveAndUpcomingAuctions(limit: 20, offset: 0, published: true) {
    count
    results {
      uuid
      state
      publishedName
      startDatetime
      endDatetime
    }
  }
}
"""

# Query to search lots within a specific auction
LOTS_QUERY = """
query SearchLotsV2($input: SearchLotInput!) {
  searchLotsV2(input: $input) {
    count
    results {
      uuid
      publishedName
      state
      lots {
        uuid
        auctionUuid
        number
        title
        state
        endDatetime
        lowEstimate
        highEstimate
        currentBid {
          amount
          currency
        }
        photos {
          photo1
        }
      }
    }
  }
}
"""


WHISKEY_TITLE_TERMS = (
    "bourbon", "rye", "whiskey", "whisky", "single malt", "scotch",
    "distillery", "distilling", "proof",
)


def _is_whiskey(title: str) -> bool:
    t = title.lower()
    return any(term in t for term in WHISKEY_TITLE_TERMS)


def _parse_lot(lot: dict) -> Listing | None:
    """Parse a GraphQL lot result into a Listing. Skips ended/closed/non-whiskey lots."""
    lot_uuid = lot.get("uuid", "")
    auction_uuid = lot.get("auctionUuid", "")
    title = lot.get("title", "")
    if not title or not lot_uuid:
        return None

    # Filter out wine and other non-whiskey lots — Unicorn auctions include
    # wine, tequila, etc. alongside bourbon
    if not _is_whiskey(title):
        return None

    # Skip lots that aren't actively biddable
    state = (lot.get("state") or "").lower()
    if state in ("closed", "ended", "sold", "unsold", "withdrawn"):
        return None

    current_bid = lot.get("currentBid") or {}
    price = current_bid.get("amount")

    ends_at = None
    if lot.get("endDatetime"):
        try:
            ends_at = datetime.fromisoformat(
                lot["endDatetime"].replace("Z", "+00:00")
            )
        except (ValueError, TypeError):
            pass

    # Skip lots that have already ended
    if ends_at and ends_at < datetime.now(timezone.utc):
        return None

    url = f"{SITE_URL}/auction/{auction_uuid}/lot/{lot_uuid}"

    photos = lot.get("photos") or {}
    image_url = None
    if photos.get("photo1"):
        image_url = (
            f"https://directus-11-4sui.onrender.com/assets/{photos['photo1']}"
            "?format=webp&quality=80&width=400"
        )

    return Listing(
        source="unicorn_auctions",
        external_id=f"{auction_uuid}:{lot_uuid}",
        title=title,
        url=url,
        price=float(price) if price is not None else None,
        image_url=image_url,
        ends_at=ends_at,
    )


class UnicornAuctionsScraper(AbstractScraper):
    @property
    def source_name(self) -> str:
        return "unicorn_auctions"

    def scrape(self) -> list[Listing]:
        listings: list[Listing] = []
        client = httpx.Client(
            headers={"Content-Type": "application/json"},
            timeout=30,
        )

        try:
            # Step 1: Get live/upcoming auctions
            auction_uuids = self._get_auction_uuids(client)
            if not auction_uuids:
                logger.warning("unicorn.no_live_auctions")
                return []

            logger.info("unicorn.found_auctions", count=len(auction_uuids))

            # Step 2: Get lots for each auction
            for auction_uuid in auction_uuids:
                lots = self._get_auction_lots(client, auction_uuid)
                listings.extend(lots)

        except httpx.HTTPError as e:
            logger.error("unicorn.http_error", error=str(e))
        finally:
            client.close()

        logger.info("unicorn.scrape_complete", count=len(listings))
        return listings

    def _graphql(self, client: httpx.Client, query: str, variables: dict | None = None) -> dict:
        """Execute a GraphQL query and return the data."""
        payload: dict = {"query": query}
        if variables:
            payload["variables"] = variables

        resp = client.post(GRAPHQL_URL, json=payload)
        resp.raise_for_status()
        result = resp.json()

        if "errors" in result:
            logger.error("unicorn.graphql_errors", errors=result["errors"])
            return {}

        return result.get("data", {})

    def _get_auction_uuids(self, client: httpx.Client) -> list[str]:
        """Fetch live and upcoming auction UUIDs."""
        logger.info("unicorn.fetching_auctions")
        data = self._graphql(client, AUCTIONS_QUERY)

        auctions = data.get("liveAndUpcomingAuctions", {})
        results = auctions.get("results", [])

        uuids = [a["uuid"] for a in results if a.get("uuid")]
        logger.info("unicorn.auctions_found", count=len(uuids))
        return uuids

    def _get_auction_lots(self, client: httpx.Client, auction_uuid: str) -> list[Listing]:
        """Fetch all lots for a given auction via SearchLotsV2."""
        listings: list[Listing] = []
        offset = 0
        limit = 96  # max per page

        while True:
            logger.info("unicorn.fetching_lots", auction=auction_uuid, offset=offset)
            data = self._graphql(client, LOTS_QUERY, variables={
                "input": {
                    "auctionUuid": auction_uuid,
                    "limit": limit,
                    "offset": offset,
                }
            })

            search = data.get("searchLotsV2", {})
            results = search.get("results", [])
            total = search.get("count", 0)

            for auction_result in results:
                lots = auction_result.get("lots", [])
                for lot in lots:
                    listing = _parse_lot(lot)
                    if listing:
                        listings.append(listing)

            # Check if we have more pages
            offset += limit
            if offset >= total or not results:
                break

        logger.info("unicorn.lots_found", auction=auction_uuid, count=len(listings))
        return listings
