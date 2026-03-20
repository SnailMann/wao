from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True)
class CrawlResult:
    text: str = ""
    url: str = ""
    error: str = ""


class CrawlerError(RuntimeError):
    """Raised when a crawler backend is unavailable or fails fatally."""


class BodyCrawler(ABC):
    """Abstract crawler interface for fetching article-like body text."""

    def __enter__(self) -> "BodyCrawler":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    def close(self) -> None:
        """Release crawler resources."""

    @abstractmethod
    def fetch(self, url: str, *, timeout: float, max_chars: int) -> CrawlResult:
        """Fetch and extract body text from a URL."""
