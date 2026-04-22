from __future__ import annotations

from datetime import datetime, timezone

from pydantic import BaseModel, Field


class Listing(BaseModel):
    source: str
    external_id: str
    title: str
    url: str
    price: float | None = None
    currency: str = "USD"
    image_url: str | None = None
    ends_at: datetime | None = None
    discovered_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
