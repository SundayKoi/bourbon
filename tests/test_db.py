import sqlite3

from src.db import filter_unseen, mark_seen, run_migrations
from src.models import Listing


def _get_test_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    run_migrations(conn)
    return conn


def _make_listing(external_id: str = "lot-1", title: str = "Test Bourbon") -> Listing:
    return Listing(
        source="test_source",
        external_id=external_id,
        title=title,
        url=f"https://example.com/{external_id}",
    )


def test_filter_unseen_returns_new_listings():
    conn = _get_test_conn()
    listings = [_make_listing("lot-1"), _make_listing("lot-2")]
    unseen = filter_unseen(conn, listings)
    assert len(unseen) == 2


def test_filter_unseen_excludes_seen():
    conn = _get_test_conn()
    listing = _make_listing("lot-1")
    mark_seen(conn, listing, watchlist_match=False)

    unseen = filter_unseen(conn, [listing, _make_listing("lot-2")])
    assert len(unseen) == 1
    assert unseen[0].external_id == "lot-2"


def test_mark_seen_dedup():
    conn = _get_test_conn()
    listing = _make_listing("lot-1")
    mark_seen(conn, listing, watchlist_match=True)
    mark_seen(conn, listing, watchlist_match=True)  # should not raise

    cursor = conn.execute("SELECT COUNT(*) FROM seen_listings")
    assert cursor.fetchone()[0] == 1


def test_empty_list():
    conn = _get_test_conn()
    assert filter_unseen(conn, []) == []
