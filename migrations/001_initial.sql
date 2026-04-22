CREATE TABLE IF NOT EXISTS seen_listings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source TEXT NOT NULL,
    external_id TEXT NOT NULL,
    title TEXT NOT NULL,
    url TEXT NOT NULL,
    price REAL,
    discovered_at TEXT NOT NULL,
    notified_at TEXT,
    watchlist_match INTEGER NOT NULL DEFAULT 0,
    UNIQUE(source, external_id)
);

CREATE INDEX IF NOT EXISTS idx_seen_source ON seen_listings(source);
CREATE INDEX IF NOT EXISTS idx_seen_discovered ON seen_listings(discovered_at);
CREATE INDEX IF NOT EXISTS idx_seen_watchlist ON seen_listings(watchlist_match);
