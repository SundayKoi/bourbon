from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import BaseModel


class DatabaseConfig(BaseModel):
    path: str = "./data/bourbon.db"


class ScraperConfig(BaseModel):
    enabled: bool = False
    interval_minutes: int = 60


class RedditScraperConfig(ScraperConfig):
    subreddits: list[str] = ["bourbon", "whiskey"]


class FilterConfig(BaseModel):
    notify_all: bool = False
    keywords: list[str] = []
    max_price: float | None = None
    min_price: float | None = None


class NtfyConfig(BaseModel):
    enabled: bool = True
    topic: str = "bourbon-alerts-CHANGEME"
    server: str = "https://ntfy.sh"
    priority: str = "high"


class EmailConfig(BaseModel):
    enabled: bool = False
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_pass: str = ""
    from_addr: str = ""
    to_addr: str = ""


class NotificationsConfig(BaseModel):
    ntfy: NtfyConfig = NtfyConfig()
    email: EmailConfig = EmailConfig()


class ScrapersConfig(BaseModel):
    unicorn_auctions: ScraperConfig = ScraperConfig(enabled=True, interval_minutes=15)
    breaking_bourbon: ScraperConfig = ScraperConfig(enabled=True, interval_minutes=360)
    reddit: RedditScraperConfig = RedditScraperConfig()
    whisky_auctioneer: ScraperConfig = ScraperConfig()
    virginia_abc: ScraperConfig = ScraperConfig()
    seelbachs: ScraperConfig = ScraperConfig()
    caskers: ScraperConfig = ScraperConfig()


class AdminConfig(BaseModel):
    ntfy_topic: str = "bourbon-admin-CHANGEME"
    notify_on_error_count: int = 3


class AppConfig(BaseModel):
    database: DatabaseConfig = DatabaseConfig()
    scrapers: ScrapersConfig = ScrapersConfig()
    filters: FilterConfig = FilterConfig()
    notifications: NotificationsConfig = NotificationsConfig()
    admin: AdminConfig = AdminConfig()


def load_config(path: str | Path = "config.yaml") -> AppConfig:
    path = Path(path)
    if not path.exists():
        return AppConfig()
    with open(path) as f:
        data = yaml.safe_load(f) or {}
    return AppConfig(**data)
