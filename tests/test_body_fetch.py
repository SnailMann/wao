from __future__ import annotations

import unittest

from daily_cli.core.models import NewsItem
from daily_cli.fetchers.body import fetch_item_bodies
from daily_cli.fetchers.crawlers import BodyCrawler, CrawlResult


class FakeCrawler(BodyCrawler):
    def __init__(self) -> None:
        self.calls: list[tuple[str, float, int]] = []

    def fetch(self, url: str, *, timeout: float, max_chars: int) -> CrawlResult:
        self.calls.append((url, timeout, max_chars))
        return CrawlResult(
            text="抓取到的正文",
            url=f"{url}?resolved=1",
            error="",
        )


class BodyFetchTests(unittest.TestCase):
    def test_fetch_item_bodies_supports_custom_crawler_factory(self) -> None:
        created: list[FakeCrawler] = []

        def factory() -> FakeCrawler:
            crawler = FakeCrawler()
            created.append(crawler)
            return crawler

        items = [
            NewsItem(
                title="example",
                category="body-test",
                link="https://example.com/article",
                provider="google",
                feed="Google News",
            )
        ]

        fetch_item_bodies(
            items,
            timeout=2.5,
            max_chars=1200,
            crawler_factory=factory,
        )

        self.assertEqual(len(created), 1)
        self.assertEqual(created[0].calls, [("https://example.com/article", 2.5, 1200)])
        self.assertEqual(items[0].body_text, "抓取到的正文")
        self.assertEqual(items[0].body_url, "https://example.com/article?resolved=1")
        self.assertEqual(items[0].body_error, "")


if __name__ == "__main__":
    unittest.main()
