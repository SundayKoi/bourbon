"""FastAPI web API for the bourbon alerts frontend.

Run with: uvicorn src.api:app --reload --port 8000
"""

from __future__ import annotations

import os

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from src.config import load_config
from src.db import (
    add_watchlist_keyword,
    get_active_listings,
    get_connection,
    get_watchlist,
    remove_watchlist_keyword,
    run_migrations,
)

app = FastAPI(title="Bourbon Alerts API")

# Allow the hosted frontend to call this API. Override via CORS_ORIGINS env var
# (comma-separated) when deploying — e.g., "https://bourbon.vercel.app".
_cors_origins = os.getenv(
    "CORS_ORIGINS",
    "http://localhost:5173,http://localhost:3000",
).split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in _cors_origins],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def get_db():
    config = load_config(os.getenv("BOURBON_CONFIG", "config.yaml"))
    conn = get_connection(config.database.path)
    run_migrations(conn)
    try:
        yield conn
    finally:
        conn.close()


class KeywordIn(BaseModel):
    keyword: str


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/listings")
def listings(
    source: str | None = None,
    watchlist_only: bool = False,
    limit: int = 500,
    conn=Depends(get_db),
) -> list[dict]:
    return get_active_listings(
        conn, source=source, watchlist_only=watchlist_only, limit=limit
    )


@app.get("/watchlist")
def watchlist(conn=Depends(get_db)) -> list[dict]:
    return get_watchlist(conn)


@app.post("/watchlist", status_code=201)
def watchlist_add(payload: KeywordIn, conn=Depends(get_db)) -> dict:
    try:
        return add_watchlist_keyword(conn, payload.keyword)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.delete("/watchlist/{keyword_id}", status_code=204)
def watchlist_remove(keyword_id: int, conn=Depends(get_db)) -> None:
    if not remove_watchlist_keyword(conn, keyword_id):
        raise HTTPException(status_code=404, detail="keyword not found")


@app.get("/sources")
def sources(conn=Depends(get_db)) -> list[str]:
    cursor = conn.execute("SELECT DISTINCT source FROM seen_listings ORDER BY source")
    return [row[0] for row in cursor.fetchall()]
