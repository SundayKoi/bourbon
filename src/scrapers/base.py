from __future__ import annotations

from abc import ABC, abstractmethod

from src.models import Listing


class AbstractScraper(ABC):
    @abstractmethod
    def scrape(self) -> list[Listing]:
        ...

    @property
    @abstractmethod
    def source_name(self) -> str:
        ...
