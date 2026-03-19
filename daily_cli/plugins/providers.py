from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from ..core.models import NewsItem
from ..core.topics import SourcePlan
from ..runtime.sources import (
    dedupe_items,
    fetch_baidu_realtime,
    fetch_github_trending,
    fetch_google_news_search,
    fetch_google_news_top,
    fetch_google_trends_us,
    filter_items_by_keywords,
)


SourceHandler = Callable[[SourcePlan, str, int, float], list[NewsItem]]


@dataclass(frozen=True)
class SourcePlugin:
    key: str
    label: str
    description: str
    handlers: dict[str, SourceHandler]


SOURCE_PLUGINS = {
    "google": SourcePlugin(
        key="google",
        label="Google",
        description="Google Trends / Google News 数据源。",
        handlers={},
    ),
    "baidu": SourcePlugin(
        key="baidu",
        label="Baidu",
        description="百度热榜数据源。",
        handlers={},
    ),
    "github": SourcePlugin(
        key="github",
        label="GitHub",
        description="GitHub Trending 数据源。",
        handlers={},
    ),
}


def list_source_plugins() -> list[SourcePlugin]:
    return [SOURCE_PLUGINS[key] for key in SOURCE_PLUGINS]


def fetch_source_plan(
    plan: SourcePlan,
    topic_key: str,
    limit: int,
    timeout: float,
) -> list[NewsItem]:
    try:
        plugin = SOURCE_PLUGINS[plan.source]
    except KeyError as exc:
        raise ValueError(f"Unsupported source plugin: {plan.source}") from exc

    try:
        handler = plugin.handlers[plan.mode]
    except KeyError as exc:
        raise ValueError(f"Unsupported {plan.source} source mode: {plan.mode}") from exc

    return handler(plan, topic_key, limit, timeout)


def _fetch_google_trends(
    plan: SourcePlan,
    topic_key: str,
    limit: int,
    timeout: float,
) -> list[NewsItem]:
    return fetch_google_trends_us(limit=limit, timeout=timeout, category=topic_key)


def _fetch_google_news_search(
    plan: SourcePlan,
    topic_key: str,
    limit: int,
    timeout: float,
) -> list[NewsItem]:
    return fetch_google_news_search(
        query=plan.query,
        limit=limit,
        timeout=timeout,
        category=topic_key,
        locale=plan.locale,
    )


def _fetch_google_news_top(
    plan: SourcePlan,
    topic_key: str,
    limit: int,
    timeout: float,
) -> list[NewsItem]:
    return fetch_google_news_top(
        limit=limit,
        timeout=timeout,
        category=topic_key,
        locale=plan.locale,
    )


def _fetch_baidu_hotboard(
    plan: SourcePlan,
    topic_key: str,
    limit: int,
    timeout: float,
) -> list[NewsItem]:
    return fetch_baidu_realtime(limit=limit, timeout=timeout, category=topic_key)


def _fetch_baidu_keyword_hotboard(
    plan: SourcePlan,
    topic_key: str,
    limit: int,
    timeout: float,
) -> list[NewsItem]:
    hot_items = fetch_baidu_realtime(limit=max(limit * 4, 20), timeout=timeout, category=topic_key)
    return filter_items_by_keywords(hot_items, keywords=plan.keywords, limit=limit, category=topic_key)


def _fetch_github_trending_plan(
    plan: SourcePlan,
    topic_key: str,
    limit: int,
    timeout: float,
) -> list[NewsItem]:
    return fetch_github_trending(limit=limit, timeout=timeout, category=topic_key)


def dedupe_source_items(items: list[NewsItem], limit: int) -> list[NewsItem]:
    return dedupe_items(items, limit=limit)


SOURCE_PLUGINS["google"].handlers.update(
    {
        "trends_us": _fetch_google_trends,
        "news_search": _fetch_google_news_search,
        "news_top": _fetch_google_news_top,
    }
)
SOURCE_PLUGINS["baidu"].handlers.update(
    {
        "hotboard": _fetch_baidu_hotboard,
        "keyword_hotboard": _fetch_baidu_keyword_hotboard,
    }
)
SOURCE_PLUGINS["github"].handlers.update(
    {
        "trending": _fetch_github_trending_plan,
    }
)
