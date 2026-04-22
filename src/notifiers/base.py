from __future__ import annotations

from abc import ABC, abstractmethod

from src.models import Listing


class AbstractNotifier(ABC):
    @abstractmethod
    def notify(self, listing: Listing) -> None:
        ...

    @abstractmethod
    def notify_admin(self, message: str) -> None:
        ...
