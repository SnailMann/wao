from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from typing import Callable

from ..core.models import NewsItem, SectionResult
from .crawlers import BodyCrawler, CrawlResult, CrawlerError, PlaywrightBodyCrawler

# Keep article fetching intentionally low-concurrency to reduce anti-bot pressure.
DEFAULT_BODY_FETCH_CONCURRENCY = 3


class BodyFetchError(CrawlerError):
    """Raised when body enrichment is unavailable or fails."""


def _apply_crawl_result(item: NewsItem, result: CrawlResult) -> None:
    item.body_text = result.text
    item.body_url = result.url
    item.body_error = result.error


def _crawl_item_batch(
    items: list[NewsItem],
    *,
    timeout: float,
    max_chars: int,
    crawler_factory: Callable[[], BodyCrawler],
) -> None:
    with crawler_factory() as crawler:
        for item in items:
            result = crawler.fetch(
                item.link,
                timeout=timeout,
                max_chars=max_chars,
            )
            _apply_crawl_result(item, result)


def _distribute_items(items: list[NewsItem], worker_count: int) -> list[list[NewsItem]]:
    buckets = [[] for _ in range(worker_count)]
    for index, item in enumerate(items):
        buckets[index % worker_count].append(item)
    return [bucket for bucket in buckets if bucket]


def fetch_item_bodies(
    items: list[NewsItem],
    timeout: float,
    max_chars: int,
    crawler_factory: Callable[[], BodyCrawler] | None = None,
    max_concurrency: int = DEFAULT_BODY_FETCH_CONCURRENCY,
) -> list[NewsItem]:
    if not items:
        return items

    factory = crawler_factory or PlaywrightBodyCrawler
    eligible_items: list[NewsItem] = []

    for item in items:
        item.body_text = ""
        item.body_url = ""
        item.body_error = ""

        if not item.link or not item.link.startswith("http"):
            item.body_error = "缺少可抓取链接"
            continue
        eligible_items.append(item)

    if not eligible_items:
        return items

    worker_count = max(1, min(len(eligible_items), max_concurrency))

    try:
        if worker_count == 1:
            _crawl_item_batch(
                eligible_items,
                timeout=timeout,
                max_chars=max_chars,
                crawler_factory=factory,
            )
            return items

        item_batches = _distribute_items(eligible_items, worker_count)
        with ThreadPoolExecutor(max_workers=worker_count) as executor:
            futures = [
                executor.submit(
                    _crawl_item_batch,
                    batch,
                    timeout=timeout,
                    max_chars=max_chars,
                    crawler_factory=factory,
                )
                for batch in item_batches
            ]
            for future in futures:
                future.result()
    except CrawlerError as exc:
        raise BodyFetchError(str(exc)) from exc
    except Exception as exc:  # pragma: no cover - defensive fallback
        raise BodyFetchError(f"正文抓取失败: {exc}") from exc

    return items


def enrich_sections_with_body(
    sections: list[SectionResult],
    *,
    timeout: float,
    max_chars: int,
) -> None:
    for section in sections:
        if not section.items:
            continue
        if section.key == "github":
            section.warnings.append("GitHub Trending 暂不抓取正文。")
            continue

        eligible_items = [item for item in section.items if item.link]
        if not eligible_items:
            continue

        try:
            fetch_item_bodies(
                eligible_items,
                timeout=timeout,
                max_chars=max_chars,
            )
        except BodyFetchError as exc:
            section.warnings.append(str(exc))
