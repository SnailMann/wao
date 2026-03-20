from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from ..core.models import NewsItem
from ..core.specs import SourcePlan
from .baidu import fetch_baidu_realtime, filter_items_by_keywords
from .common import dedupe_items
from .github import fetch_github_trending
from .google import fetch_google_news_search, fetch_google_news_top, fetch_google_trends_us
from .rss import fetch_feed_url, fetch_rsshub_route
from .x import fetch_x_news_search, fetch_x_recent_search, fetch_x_user_tweets

SourceHandler = Callable[[SourcePlan, str, int, float], list[NewsItem]]


@dataclass(frozen=True)
class SourceFetcher:
    key: str
    label: str
    description: str
    handlers: dict[str, SourceHandler]


SOURCE_FETCHERS = {
    "google": SourceFetcher("google", "Google", "Google Trends / Google News 数据源。", {}),
    "baidu": SourceFetcher("baidu", "Baidu", "百度热榜数据源。", {}),
    "github": SourceFetcher("github", "GitHub", "GitHub Trending 数据源。", {}),
    "x": SourceFetcher("x", "X", "X 官方 recent search 数据源。", {}),
    "x-user": SourceFetcher("x-user", "X User", "X 官方用户时间线数据源。", {}),
    "x-news": SourceFetcher("x-news", "X News", "X 官方 News API 数据源。", {}),
    "rsshub": SourceFetcher("rsshub", "RSSHub", "RSSHub 订阅源。", {}),
    "feed": SourceFetcher("feed", "Feed", "普通 RSS / Atom 订阅源。", {}),
}


def list_source_fetchers() -> list[SourceFetcher]:
    return [SOURCE_FETCHERS[key] for key in SOURCE_FETCHERS]


def fetch_source_plan(
    plan: SourcePlan,
    topic_key: str,
    limit: int,
    timeout: float,
) -> list[NewsItem]:
    try:
        fetcher = SOURCE_FETCHERS[plan.source]
    except KeyError as exc:
        raise ValueError(f"Unsupported source fetcher: {plan.source}") from exc

    try:
        handler = fetcher.handlers[plan.mode]
    except KeyError as exc:
        raise ValueError(f"Unsupported {plan.source} source mode: {plan.mode}") from exc

    return handler(plan, topic_key, limit, timeout)


def dedupe_source_items(items: list[NewsItem], limit: int) -> list[NewsItem]:
    return dedupe_items(items, limit=limit)


def _fetch_google_trends(plan: SourcePlan, topic_key: str, limit: int, timeout: float) -> list[NewsItem]:
    return fetch_google_trends_us(limit=limit, timeout=timeout, category=topic_key)


def _fetch_google_news_search(plan: SourcePlan, topic_key: str, limit: int, timeout: float) -> list[NewsItem]:
    return fetch_google_news_search(
        query=plan.query,
        limit=limit,
        timeout=timeout,
        category=topic_key,
        locale=plan.locale,
    )


def _fetch_google_news_top(plan: SourcePlan, topic_key: str, limit: int, timeout: float) -> list[NewsItem]:
    return fetch_google_news_top(limit=limit, timeout=timeout, category=topic_key, locale=plan.locale)


def _fetch_baidu_hotboard(plan: SourcePlan, topic_key: str, limit: int, timeout: float) -> list[NewsItem]:
    return fetch_baidu_realtime(limit=limit, timeout=timeout, category=topic_key)


def _fetch_baidu_keyword_hotboard(plan: SourcePlan, topic_key: str, limit: int, timeout: float) -> list[NewsItem]:
    hot_items = fetch_baidu_realtime(limit=max(limit * 4, 20), timeout=timeout, category=topic_key)
    return filter_items_by_keywords(hot_items, keywords=plan.keywords, limit=limit, category=topic_key)


def _fetch_github_trending(plan: SourcePlan, topic_key: str, limit: int, timeout: float) -> list[NewsItem]:
    return fetch_github_trending(limit=limit, timeout=timeout, category=topic_key)


def _fetch_x_user_tweets(plan: SourcePlan, topic_key: str, limit: int, timeout: float) -> list[NewsItem]:
    return fetch_x_user_tweets(plan.query, limit=limit, timeout=timeout, category=topic_key)


def _fetch_x_recent_search(plan: SourcePlan, topic_key: str, limit: int, timeout: float) -> list[NewsItem]:
    return fetch_x_recent_search(plan.query, limit=limit, timeout=timeout, category=topic_key)


def _fetch_x_news_search(plan: SourcePlan, topic_key: str, limit: int, timeout: float) -> list[NewsItem]:
    return fetch_x_news_search(plan.query, limit=limit, timeout=timeout, category=topic_key)


def _fetch_rsshub_route(plan: SourcePlan, topic_key: str, limit: int, timeout: float) -> list[NewsItem]:
    return fetch_rsshub_route(plan.query, instance=plan.endpoint, limit=limit, timeout=timeout, category=topic_key)


def _fetch_feed_url(plan: SourcePlan, topic_key: str, limit: int, timeout: float) -> list[NewsItem]:
    return fetch_feed_url(plan.query, limit=limit, timeout=timeout, category=topic_key)


SOURCE_FETCHERS["google"].handlers.update(
    {"trends_us": _fetch_google_trends, "news_search": _fetch_google_news_search, "news_top": _fetch_google_news_top}
)
SOURCE_FETCHERS["baidu"].handlers.update(
    {"hotboard": _fetch_baidu_hotboard, "keyword_hotboard": _fetch_baidu_keyword_hotboard}
)
SOURCE_FETCHERS["github"].handlers.update({"trending": _fetch_github_trending})
SOURCE_FETCHERS["x"].handlers.update({"search_recent": _fetch_x_recent_search})
SOURCE_FETCHERS["x-user"].handlers.update({"user_posts": _fetch_x_user_tweets})
SOURCE_FETCHERS["x-news"].handlers.update({"news_search": _fetch_x_news_search})
SOURCE_FETCHERS["rsshub"].handlers.update({"route": _fetch_rsshub_route})
SOURCE_FETCHERS["feed"].handlers.update({"url": _fetch_feed_url})
