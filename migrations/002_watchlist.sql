CREATE TABLE IF NOT EXISTS watchlist (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    keyword TEXT NOT NULL UNIQUE,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    active INTEGER NOT NULL DEFAULT 1
);

CREATE INDEX IF NOT EXISTS idx_watchlist_active ON watchlist(active);

ALTER TABLE seen_listings ADD COLUMN image_url TEXT;
ALTER TABLE seen_listings ADD COLUMN ends_at TEXT;
