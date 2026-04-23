from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from src.models import Listing

MIGRATIONS_DIR = Path(__file__).resolve().parent.parent / "migrations"


def get_connection(db_path: str) -> sqlite3.Connection:
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def run_migrations(conn: sqlite3.Connection) -> None:
    conn.execute(
        "CREATE TABLE IF NOT EXISTS schema_migrations (name TEXT PRIMARY KEY, applied_at TEXT NOT NULL)"
    )
    applied = {row[0] for row in conn.execute("SELECT name FROM schema_migrations")}

    migration_files = sorted(MIGRATIONS_DIR.glob("*.sql"))
    now = datetime.now(timezone.utc).isoformat()
    for mf in migration_files:
        if mf.name in applied:
            continue
        conn.executescript(mf.read_text())
        conn.execute(
            "INSERT INTO schema_migrations (name, applied_at) VALUES (?, ?)",
            (mf.name, now),
        )
    conn.commit()


def filter_unseen(conn: sqlite3.Connection, listings: list[Listing]) -> list[Listing]:
    """Return only listings not already in the database."""
    if not listings:
        return []
    unseen = []
    for listing in listings:
        cursor = conn.execute(
            "SELECT 1 FROM seen_listings WHERE source = ? AND external_id = ?",
            (listing.source, listing.external_id),
        )
        if cursor.fetchone() is None:
            unseen.append(listing)
    return unseen


def mark_seen(
    conn: sqlite3.Connection,
    listing: Listing,
    watchlist_match: bool,
) -> None:
    """Insert a listing into seen_listings, or backfill image/ends_at if already present."""
    now = datetime.now(timezone.utc).isoformat()
    conn.execute(
        """INSERT INTO seen_listings
           (source, external_id, title, url, price, discovered_at, notified_at,
            watchlist_match, image_url, ends_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
           ON CONFLICT(source, external_id) DO UPDATE SET
             image_url = COALESCE(seen_listings.image_url, excluded.image_url),
             ends_at = COALESCE(seen_listings.ends_at, excluded.ends_at),
             price = COALESCE(excluded.price, seen_listings.price)""",
        (
            listing.source,
            listing.external_id,
            listing.title,
            listing.url,
            listing.price,
            listing.discovered_at.isoformat(),
            now,
            int(watchlist_match),
            listing.image_url,
            listing.ends_at.isoformat() if listing.ends_at else None,
        ),
    )
    conn.commit()


def get_watchlist_keywords(conn: sqlite3.Connection) -> list[str]:
    """Get all active watchlist keywords."""
    cursor = conn.execute(
        "SELECT keyword FROM watchlist WHERE active = 1 ORDER BY keyword"
    )
    return [row[0] for row in cursor.fetchall()]


def get_watchlist(conn: sqlite3.Connection) -> list[dict]:
    """Get all watchlist entries with metadata."""
    cursor = conn.execute(
        "SELECT id, keyword, created_at, active FROM watchlist ORDER BY keyword"
    )
    return [
        {"id": row[0], "keyword": row[1], "created_at": row[2], "active": bool(row[3])}
        for row in cursor.fetchall()
    ]


def add_watchlist_keyword(conn: sqlite3.Connection, keyword: str) -> dict:
    """Add a keyword to the watchlist. Re-activates if previously removed."""
    keyword = keyword.strip()
    if not keyword:
        raise ValueError("keyword cannot be empty")
    conn.execute(
        """INSERT INTO watchlist (keyword, active) VALUES (?, 1)
           ON CONFLICT(keyword) DO UPDATE SET active = 1""",
        (keyword,),
    )
    conn.commit()
    cursor = conn.execute(
        "SELECT id, keyword, created_at, active FROM watchlist WHERE keyword = ?",
        (keyword,),
    )
    row = cursor.fetchone()
    return {"id": row[0], "keyword": row[1], "created_at": row[2], "active": bool(row[3])}


def remove_watchlist_keyword(conn: sqlite3.Connection, keyword_id: int) -> bool:
    """Soft-delete a watchlist keyword by setting active=0. Returns True if found."""
    cursor = conn.execute(
        "UPDATE watchlist SET active = 0 WHERE id = ?", (keyword_id,)
    )
    conn.commit()
    return cursor.rowcount > 0


def get_active_listings(
    conn: sqlite3.Connection,
    source: str | None = None,
    watchlist_only: bool = False,
    limit: int = 500,
) -> list[dict]:
    """Get listings that haven't expired (ends_at in future or null), newest first."""
    now = datetime.now(timezone.utc).isoformat()
    where = ["(ends_at IS NULL OR ends_at > ?)"]
    params: list = [now]

    if source:
        where.append("source = ?")
        params.append(source)

    if watchlist_only:
        where.append("watchlist_match = 1")

    query = f"""
        SELECT id, source, external_id, title, url, price, image_url,
               ends_at, discovered_at, watchlist_match
        FROM seen_listings
        WHERE {" AND ".join(where)}
        ORDER BY discovered_at DESC
        LIMIT ?
    """
    params.append(limit)

    cursor = conn.execute(query, params)
    return [
        {
            "id": row[0],
            "source": row[1],
            "external_id": row[2],
            "title": row[3],
            "url": row[4],
            "price": row[5],
            "image_url": row[6],
            "ends_at": row[7],
            "discovered_at": row[8],
            "watchlist_match": bool(row[9]),
        }
        for row in cursor.fetchall()
    ]


def get_undigested_listings(conn: sqlite3.Connection) -> list[dict]:
    """Get non-watchlist listings that haven't been included in a digest yet."""
    cursor = conn.execute(
        """SELECT source, title, url, price, discovered_at
           FROM seen_listings
           WHERE watchlist_match = 0
           ORDER BY discovered_at DESC"""
    )
    return [
        {
            "source": row[0],
            "title": row[1],
            "url": row[2],
            "price": row[3],
            "discovered_at": row[4],
        }
        for row in cursor.fetchall()
    ]
