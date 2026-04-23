"""Bourbon Alerts — main entry point and scheduler."""

from __future__ import annotations

import argparse
import sys
import time

import structlog
from apscheduler.schedulers.blocking import BlockingScheduler

from src.config import AppConfig, load_config
from src.db import (
    add_watchlist_keyword,
    filter_unseen,
    get_connection,
    get_watchlist_keywords,
    mark_seen,
    run_migrations,
)
from src.digest import send_digest
from src.filters import apply_filters
from src.notifiers.ntfy import NtfyNotifier
from src.scrapers.base import AbstractScraper
from src.scrapers.breaking_bourbon import BreakingBourbonScraper
from src.scrapers.reddit import RedditScraper
from src.scrapers.unicorn import UnicornAuctionsScraper
from src.scrapers.virginia_abc import VirginiaABCScraper
from src.scrapers.whisky_auctioneer import WhiskyAuctioneerScraper
from src.scrapers.seelbachs import SeelbachsScraper
from src.scrapers.caskers import CaskersScraper

logger = structlog.get_logger()


def get_enabled_scrapers(config: AppConfig) -> list[AbstractScraper]:
    scrapers: list[AbstractScraper] = []
    if config.scrapers.unicorn_auctions.enabled:
        scrapers.append(UnicornAuctionsScraper())
    if config.scrapers.breaking_bourbon.enabled:
        scrapers.append(BreakingBourbonScraper())
    if config.scrapers.reddit.enabled:
        scrapers.append(RedditScraper(config.scrapers.reddit.subreddits))
    if config.scrapers.whisky_auctioneer.enabled:
        scrapers.append(WhiskyAuctioneerScraper())
    if config.scrapers.virginia_abc.enabled:
        scrapers.append(VirginiaABCScraper())
    if config.scrapers.seelbachs.enabled:
        scrapers.append(SeelbachsScraper())
    if config.scrapers.caskers.enabled:
        scrapers.append(CaskersScraper())
    return scrapers


def seed_watchlist_from_config(conn, config: AppConfig) -> None:
    """If the DB watchlist is empty, populate it from the YAML config keywords."""
    existing = get_watchlist_keywords(conn)
    if existing:
        return
    for kw in config.filters.keywords:
        try:
            add_watchlist_keyword(conn, kw)
        except Exception as e:
            logger.warning("watchlist.seed_error", keyword=kw, error=str(e))
    logger.info("watchlist.seeded", count=len(config.filters.keywords))


def run_backfill(config: AppConfig) -> None:
    """Re-scrape all sources and upsert image_url/ends_at on existing records.

    Unlike run_scrape_cycle, this skips dedup and applies mark_seen to every
    scraped listing so missing fields on existing rows get filled in.
    No notifications are sent.
    """
    conn = get_connection(config.database.path)
    run_migrations(conn)
    seed_watchlist_from_config(conn, config)

    keywords = get_watchlist_keywords(conn)
    scrapers = get_enabled_scrapers(config)

    for scraper in scrapers:
        source = scraper.source_name
        try:
            logger.info("backfill.scraping", source=source)
            raw_listings = scraper.scrape()
            result = apply_filters(raw_listings, config.filters, keywords=keywords)

            for listing in result.instant:
                mark_seen(conn, listing, watchlist_match=True)
            for listing in result.digest:
                mark_seen(conn, listing, watchlist_match=False)

            logger.info("backfill.done", source=source, count=len(raw_listings))
        except Exception as e:
            logger.error("backfill.scraper_error", source=source, error=str(e))

    conn.close()


def run_scrape_cycle(config: AppConfig, silent: bool = False) -> None:
    """Run one full scrape → dedup → filter → notify cycle.

    When silent=True, all listings are stored in the DB but no notifications
    are sent. Use this for seeding the database on first run.
    """
    conn = get_connection(config.database.path)
    run_migrations(conn)
    seed_watchlist_from_config(conn, config)

    keywords = get_watchlist_keywords(conn)

    scrapers = get_enabled_scrapers(config)
    notifier = NtfyNotifier(config.notifications.ntfy, config.admin.ntfy_topic)

    error_counts: dict[str, int] = {}

    for scraper in scrapers:
        source = scraper.source_name
        try:
            logger.info("cycle.scraping", source=source)
            raw_listings = scraper.scrape()

            # Dedup
            new_listings = filter_unseen(conn, raw_listings)
            logger.info("cycle.new_listings", source=source, count=len(new_listings))

            if not new_listings:
                error_counts.pop(source, None)
                continue

            # Two-tier filter (keywords from DB, overriding YAML)
            result = apply_filters(new_listings, config.filters, keywords=keywords)

            if silent:
                # Seed mode: store everything without sending notifications
                for listing in result.instant:
                    mark_seen(conn, listing, watchlist_match=True)
                for listing in result.digest:
                    mark_seen(conn, listing, watchlist_match=False)
                logger.info("cycle.seeded", source=source,
                            instant=len(result.instant), digest=len(result.digest))
            else:
                # Instant push for watchlist matches
                for listing in result.instant:
                    try:
                        notifier.notify(listing)
                        mark_seen(conn, listing, watchlist_match=True)
                    except Exception as e:
                        logger.error("cycle.notify_error", listing=listing.title, error=str(e))

                # Store digest items
                for listing in result.digest:
                    mark_seen(conn, listing, watchlist_match=False)

            error_counts.pop(source, None)

        except Exception as e:
            logger.error("cycle.scraper_error", source=source, error=str(e))
            error_counts[source] = error_counts.get(source, 0) + 1
            if error_counts[source] >= config.admin.notify_on_error_count:
                try:
                    notifier.notify_admin(
                        f"Scraper '{source}' has failed {error_counts[source]} times in a row.\n"
                        f"Latest error: {e}"
                    )
                except Exception:
                    pass

    conn.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Bourbon Alerts")
    parser.add_argument(
        "--once",
        action="store_true",
        help="Run a single scrape cycle and exit",
    )
    parser.add_argument(
        "--digest",
        action="store_true",
        help="Send the digest email and exit",
    )
    parser.add_argument(
        "--seed",
        action="store_true",
        help="Seed the database with current listings without sending notifications",
    )
    parser.add_argument(
        "--backfill",
        action="store_true",
        help="Re-scrape and backfill image_url/ends_at on existing records, no notifications",
    )
    parser.add_argument(
        "--config",
        default="config.yaml",
        help="Path to config file (default: config.yaml)",
    )
    args = parser.parse_args()

    structlog.configure(
        processors=[
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.add_log_level,
            structlog.dev.ConsoleRenderer(),
        ],
    )

    config = load_config(args.config)
    logger.info("starting", mode="once" if args.once else "scheduler")

    if args.seed:
        logger.info("seed.starting", mode="seed")
        run_scrape_cycle(config, silent=True)
        logger.info("seed.complete")
        return

    if args.backfill:
        logger.info("backfill.starting")
        run_backfill(config)
        logger.info("backfill.complete")
        return

    if args.once:
        run_scrape_cycle(config)
        return

    if args.digest:
        conn = get_connection(config.database.path)
        run_migrations(conn)
        send_digest(conn, config)
        conn.close()
        return

    # Scheduled mode
    scheduler = BlockingScheduler()

    # Auction scrapers — run at their configured intervals
    scheduler.add_job(
        run_scrape_cycle,
        "interval",
        args=[config],
        minutes=config.scrapers.unicorn_auctions.interval_minutes,
        id="scrape_cycle",
        name="Bourbon scrape cycle",
    )

    # Daily digest at 8 PM
    if config.notifications.email.enabled:
        def digest_job():
            conn = get_connection(config.database.path)
            run_migrations(conn)
            send_digest(conn, config)
            conn.close()

        scheduler.add_job(
            digest_job,
            "cron",
            hour=20,
            minute=0,
            id="daily_digest",
            name="Daily bourbon digest",
        )

    # Run immediately on start, then on schedule
    run_scrape_cycle(config)

    logger.info("scheduler.starting")
    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("scheduler.stopped")


if __name__ == "__main__":
    main()
