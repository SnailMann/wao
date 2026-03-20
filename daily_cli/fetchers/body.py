from __future__ import annotations

from typing import Callable

from ..core.models import NewsItem, SectionResult
from .crawlers import BodyCrawler, CrawlResult, CrawlerError, PlaywrightBodyCrawler


class BodyFetchError(CrawlerError):
    """Raised when body enrichment is unavailable or fails."""


def _apply_crawl_result(item: NewsItem, result: CrawlResult) -> None:
    item.body_text = result.text
    item.body_url = result.url
    item.body_error = result.error


def fetch_item_bodies(
    items: list[NewsItem],
    timeout: float,
    max_chars: int,
    crawler_factory: Callable[[], BodyCrawler] | None = None,
) -> list[NewsItem]:
    if not items:
        return items

    factory = crawler_factory or PlaywrightBodyCrawler

    try:
        with factory() as crawler:
            for item in items:
                item.body_text = ""
                item.body_url = ""
                item.body_error = ""

                if not item.link or not item.link.startswith("http"):
                    item.body_error = "缺少可抓取链接"
                    continue

                result = crawler.fetch(
                    item.link,
                    timeout=timeout,
                    max_chars=max_chars,
                )
                _apply_crawl_result(item, result)
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
