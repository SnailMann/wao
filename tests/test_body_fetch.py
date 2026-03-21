from __future__ import annotations

import unittest

from wao.core.models import NewsItem
from wao.fetchers.body import fetch_item_bodies
from wao.fetchers.crawlers import BodyCrawler, CrawlResult


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

    def test_fetch_item_bodies_reuses_single_crawler_when_concurrency_is_one(self) -> None:
        created: list[FakeCrawler] = []

        def factory() -> FakeCrawler:
            crawler = FakeCrawler()
            created.append(crawler)
            return crawler

        items = [
            NewsItem(
                title=f"example-{index}",
                category="body-test",
                link=f"https://example.com/article-{index}",
                provider="google",
                feed="Google News",
            )
            for index in range(3)
        ]

        fetch_item_bodies(
            items,
            timeout=2.5,
            max_chars=1200,
            crawler_factory=factory,
            max_concurrency=1,
        )

        self.assertEqual(len(created), 1)
        self.assertEqual(
            created[0].calls,
            [
                ("https://example.com/article-0", 2.5, 1200),
                ("https://example.com/article-1", 2.5, 1200),
                ("https://example.com/article-2", 2.5, 1200),
            ],
        )

    def test_fetch_item_bodies_limits_crawler_instances_to_worker_count(self) -> None:
        created: list[FakeCrawler] = []

        def factory() -> FakeCrawler:
            crawler = FakeCrawler()
            created.append(crawler)
            return crawler

        items = [
            NewsItem(
                title=f"example-{index}",
                category="body-test",
                link=f"https://example.com/article-{index}",
                provider="google",
                feed="Google News",
            )
            for index in range(5)
        ]

        fetch_item_bodies(
            items,
            timeout=2.5,
            max_chars=1200,
            crawler_factory=factory,
            max_concurrency=2,
        )

        self.assertEqual(len(created), 2)
        self.assertEqual(
            sorted(call for crawler in created for call in crawler.calls),
            [
                ("https://example.com/article-0", 2.5, 1200),
                ("https://example.com/article-1", 2.5, 1200),
                ("https://example.com/article-2", 2.5, 1200),
                ("https://example.com/article-3", 2.5, 1200),
                ("https://example.com/article-4", 2.5, 1200),
            ],
        )
        self.assertTrue(all(item.body_text == "抓取到的正文" for item in items))


if __name__ == "__main__":
    unittest.main()
