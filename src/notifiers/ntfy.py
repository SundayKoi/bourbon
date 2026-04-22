"""ntfy.sh push notification sender."""

from __future__ import annotations

import httpx
import structlog

from src.config import NtfyConfig
from src.models import Listing
from src.notifiers.base import AbstractNotifier

logger = structlog.get_logger()

PRIORITY_MAP = {
    "min": 1, "low": 2, "default": 3, "high": 4, "urgent": 5,
}


def _priority_to_int(priority: str) -> int:
    return PRIORITY_MAP.get(priority, 3)


class NtfyNotifier(AbstractNotifier):
    def __init__(self, config: NtfyConfig, admin_topic: str = "") -> None:
        self.config = config
        self.admin_topic = admin_topic

    def notify(self, listing: Listing) -> None:
        """Send a push notification for a bourbon listing."""
        source_label = listing.source.replace("_", " ").title()
        title = f"{source_label}: {listing.title}"
        parts = []
        if listing.price is not None:
            parts.append(f"Price: ${listing.price:,.2f}")
        if listing.ends_at:
            parts.append(f"Ends: {listing.ends_at.strftime('%b %d, %I:%M %p')}")
        message = "\n".join(parts) if parts else listing.title

        self._send(
            topic=self.config.topic,
            title=title,
            message=message,
            url=listing.url,
            priority=self.config.priority,
            tags=["tumbler_glass", "bourbon"],
        )

    def notify_admin(self, message: str) -> None:
        """Send an admin alert (e.g., scraper failure)."""
        if not self.admin_topic:
            logger.warning("ntfy.no_admin_topic")
            return
        self._send(
            topic=self.admin_topic,
            title="Bourbon Alerts Admin",
            message=message,
            priority="default",
            tags=["warning"],
        )

    def _send(
        self,
        topic: str,
        title: str,
        message: str,
        url: str = "",
        priority: str = "default",
        tags: list[str] | None = None,
    ) -> None:
        endpoint = self.config.server
        payload: dict = {
            "topic": topic,
            "title": title,
            "message": message,
            "priority": _priority_to_int(priority),
        }
        if tags:
            payload["tags"] = tags
        if url:
            payload["click"] = url

        try:
            resp = httpx.post(endpoint, json=payload, timeout=10)
            resp.raise_for_status()
            logger.info("ntfy.sent", topic=topic, title=title)
        except httpx.HTTPError as e:
            logger.error("ntfy.send_error", topic=topic, error=str(e))
            raise
