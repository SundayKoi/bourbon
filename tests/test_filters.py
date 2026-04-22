from src.config import FilterConfig
from src.filters import apply_filters
from src.models import Listing


def _make_listing(title: str, price: float | None = None) -> Listing:
    return Listing(
        source="test",
        external_id=title.lower().replace(" ", "-"),
        title=title,
        url=f"https://example.com/{title.lower().replace(' ', '-')}",
        price=price,
    )


def test_watchlist_match_goes_to_instant():
    config = FilterConfig(keywords=["Pappy Van Winkle"], notify_all=False)
    listings = [
        _make_listing("Pappy Van Winkle 23 Year"),
        _make_listing("Random Bourbon XYZ"),
    ]
    result = apply_filters(listings, config)
    assert len(result.instant) == 1
    assert result.instant[0].title == "Pappy Van Winkle 23 Year"
    assert len(result.digest) == 1
    assert result.digest[0].title == "Random Bourbon XYZ"


def test_notify_all_sends_everything_to_instant():
    config = FilterConfig(keywords=["Pappy"], notify_all=True)
    listings = [
        _make_listing("Pappy Van Winkle 23 Year"),
        _make_listing("Random Bourbon XYZ"),
    ]
    result = apply_filters(listings, config)
    assert len(result.instant) == 2
    assert len(result.digest) == 0


def test_case_insensitive_matching():
    config = FilterConfig(keywords=["george t stagg"], notify_all=False)
    listings = [_make_listing("George T Stagg 2024 Release")]
    result = apply_filters(listings, config)
    assert len(result.instant) == 1


def test_max_price_filter():
    config = FilterConfig(keywords=["Bourbon"], max_price=500, notify_all=False)
    listings = [
        _make_listing("Bourbon Under Budget", price=300),
        _make_listing("Bourbon Over Budget", price=1000),
    ]
    result = apply_filters(listings, config)
    assert len(result.instant) == 1
    assert result.instant[0].title == "Bourbon Under Budget"


def test_min_price_filter():
    config = FilterConfig(keywords=["Bourbon"], min_price=100, notify_all=False)
    listings = [
        _make_listing("Cheap Bourbon", price=50),
        _make_listing("Good Bourbon", price=200),
    ]
    result = apply_filters(listings, config)
    assert len(result.instant) == 1
    assert result.instant[0].title == "Good Bourbon"


def test_no_keywords_nothing_goes_instant():
    config = FilterConfig(keywords=[], notify_all=False)
    listings = [_make_listing("Some Bourbon")]
    result = apply_filters(listings, config)
    assert len(result.instant) == 0
    assert len(result.digest) == 1


def test_price_none_not_filtered():
    config = FilterConfig(keywords=["Bourbon"], max_price=500, notify_all=False)
    listings = [_make_listing("Bourbon No Price", price=None)]
    result = apply_filters(listings, config)
    assert len(result.instant) == 1
