"""Digest builder — collects non-watchlist listings and sends a summary email."""

from __future__ import annotations

import sqlite3

import structlog

from src.config import AppConfig
from src.db import get_undigested_listings
from src.notifiers.email import EmailNotifier

logger = structlog.get_logger()


def send_digest(conn: sqlite3.Connection, config: AppConfig) -> None:
    """Build and send the daily digest email."""
    if not config.notifications.email.enabled:
        logger.info("digest.email_disabled")
        return

    listings = get_undigested_listings(conn)
    if not listings:
        logger.info("digest.no_listings")
        return

    notifier = EmailNotifier(config.notifications.email)
    notifier.send_digest(listings)
    logger.info("digest.sent", count=len(listings))
