"""Two-tier filtering: watchlist matches get instant push, rest go to digest."""

from __future__ import annotations

from dataclasses import dataclass

from src.config import FilterConfig
from src.models import Listing


@dataclass
class FilterResult:
    instant: list[Listing]  # watchlist matches → push notification
    digest: list[Listing]   # everything else → daily digest


def apply_filters(
    listings: list[Listing],
    config: FilterConfig,
    keywords: list[str] | None = None,
) -> FilterResult:
    """Split listings into instant (watchlist match) and digest buckets.

    If keywords is provided, it overrides config.keywords. Use this to pass
    keywords loaded from the DB watchlist table.
    """
    instant: list[Listing] = []
    digest: list[Listing] = []

    effective_keywords = keywords if keywords is not None else config.keywords
    keywords_lower = [kw.lower() for kw in effective_keywords]

    for listing in listings:
        # Price filters
        if config.max_price is not None and listing.price is not None:
            if listing.price > config.max_price:
                continue
        if config.min_price is not None and listing.price is not None:
            if listing.price < config.min_price:
                continue

        # Watchlist keyword matching
        title_lower = listing.title.lower()
        is_watchlist = any(kw in title_lower for kw in keywords_lower)

        if config.notify_all or is_watchlist:
            instant.append(listing)
        else:
            digest.append(listing)

    return FilterResult(instant=instant, digest=digest)
