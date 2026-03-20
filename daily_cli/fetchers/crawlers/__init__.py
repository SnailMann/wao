"""Crawler backends for article/body extraction."""

from .base import BodyCrawler, CrawlResult, CrawlerError
from .playwright import PlaywrightBodyCrawler

__all__ = [
    "BodyCrawler",
    "CrawlResult",
    "CrawlerError",
    "PlaywrightBodyCrawler",
]
