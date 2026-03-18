from __future__ import annotations

from dataclasses import dataclass

from .models import NewsItem, SectionResult
from .sources import (
    FetchError,
    contains_cjk,
    dedupe_items,
    fetch_baidu_realtime,
    fetch_baidu_suggestions,
    fetch_google_news_search,
    fetch_google_trends_us,
    filter_items_by_keywords,
    local_now_string,
    normalize_title,
)

DEFAULT_SUMMARY_PRESETS = ("us-hot", "china-hot", "ai", "finance")

AI_GOOGLE_QUERY = 'AI OR "artificial intelligence" OR OpenAI OR Anthropic OR Gemini OR Nvidia'
FINANCE_GOOGLE_QUERY = (
    '"stock market" OR Nasdaq OR "S&P 500" OR "Dow Jones" OR '
    '"Federal Reserve" OR earnings OR inflation'
)
US_MARKET_GOOGLE_QUERY = '"US stocks" OR "stock market" OR Nasdaq OR "S&P 500" OR "Dow Jones"'

AI_BAIDU_QUERY = "人工智能"
FINANCE_BAIDU_QUERY = "金融"
US_MARKET_BAIDU_QUERY = "美股"

AI_KEYWORDS = (
    "ai",
    "artificial intelligence",
    "openai",
    "anthropic",
    "gemini",
    "nvidia",
    "人工智能",
    "大模型",
    "机器人",
    "智能体",
)
FINANCE_KEYWORDS = (
    "stock",
    "market",
    "nasdaq",
    "dow",
    "s&p",
    "fed",
    "finance",
    "financial",
    "earnings",
    "inflation",
    "金融",
    "财经",
    "股市",
    "美股",
    "a股",
    "黄金",
    "油价",
    "银行",
    "基金",
    "人民币",
    "债",
)
US_MARKET_KEYWORDS = (
    "美股",
    "纳指",
    "道指",
    "标普",
    "nasdaq",
    "dow",
    "s&p",
    "股票",
    "股指",
)


@dataclass(frozen=True)
class PresetSpec:
    key: str
    label: str
    description: str
    supported_sources: tuple[str, ...]
    default_sources: tuple[str, ...]


PRESET_SPECS = {
    "us-hot": PresetSpec(
        key="us-hot",
        label="美国热门事件",
        description="默认使用 Google Trends RSS，适合追踪美国当天热门搜索与事件。",
        supported_sources=("google",),
        default_sources=("google",),
    ),
    "china-hot": PresetSpec(
        key="china-hot",
        label="中国热门事件",
        description="默认使用百度热榜结构化数据。",
        supported_sources=("baidu",),
        default_sources=("baidu",),
    ),
    "ai": PresetSpec(
        key="ai",
        label="AI 发展趋势",
        description="聚合 Google News RSS 与百度联想热点、百度热榜中的 AI 相关条目。",
        supported_sources=("google", "baidu"),
        default_sources=("google", "baidu"),
    ),
    "finance": PresetSpec(
        key="finance",
        label="金融热门事件",
        description="聚合 Google News RSS 与百度联想热点、百度热榜中的金融类条目。",
        supported_sources=("google", "baidu"),
        default_sources=("google", "baidu"),
    ),
    "us-market": PresetSpec(
        key="us-market",
        label="美股焦点",
        description="额外预设，聚合美股相关热点与新闻。",
        supported_sources=("google", "baidu"),
        default_sources=("google", "baidu"),
    ),
}


def list_presets() -> list[PresetSpec]:
    return [PRESET_SPECS[key] for key in PRESET_SPECS]


def resolve_sources(spec: PresetSpec, requested_source: str) -> tuple[str, ...]:
    if requested_source == "auto":
        return spec.default_sources
    if requested_source == "all":
        return spec.supported_sources
    if requested_source not in spec.supported_sources:
        supported = ", ".join(spec.supported_sources)
        raise ValueError(f"{spec.key} 仅支持这些来源: {supported}")
    return (requested_source,)


def _google_items_for_preset(key: str, limit: int, timeout: float) -> list[NewsItem]:
    if key == "us-hot":
        return fetch_google_trends_us(limit=limit, timeout=timeout, category=key)
    if key == "ai":
        return fetch_google_news_search(
            query=AI_GOOGLE_QUERY,
            limit=limit,
            timeout=timeout,
            category=key,
            locale="us",
        )
    if key == "finance":
        return fetch_google_news_search(
            query=FINANCE_GOOGLE_QUERY,
            limit=limit,
            timeout=timeout,
            category=key,
            locale="us",
        )
    if key == "us-market":
        return fetch_google_news_search(
            query=US_MARKET_GOOGLE_QUERY,
            limit=limit,
            timeout=timeout,
            category=key,
            locale="us",
        )
    raise ValueError(f"Unsupported Google preset: {key}")


def _baidu_topic_mix(
    query: str,
    keywords: tuple[str, ...],
    limit: int,
    timeout: float,
    category: str,
) -> list[NewsItem]:
    suggested = fetch_baidu_suggestions(
        query=query,
        limit=limit,
        timeout=timeout,
        category=category,
        include_suggestions=False,
    )
    hot_items = fetch_baidu_realtime(limit=max(limit * 4, 20), timeout=timeout, category=category)
    filtered = filter_items_by_keywords(hot_items, keywords=keywords, limit=limit, category=category)
    merged = dedupe_items([*suggested, *filtered], limit=limit)
    if len(merged) >= limit:
        return merged

    fallback = fetch_baidu_suggestions(
        query=query,
        limit=limit,
        timeout=timeout,
        category=category,
        include_suggestions=True,
    )
    return dedupe_items([*merged, *fallback], limit=limit)


def _baidu_items_for_preset(key: str, limit: int, timeout: float) -> list[NewsItem]:
    if key == "china-hot":
        return fetch_baidu_realtime(limit=limit, timeout=timeout, category=key)
    if key == "ai":
        return _baidu_topic_mix(
            query=AI_BAIDU_QUERY,
            keywords=AI_KEYWORDS,
            limit=limit,
            timeout=timeout,
            category=key,
        )
    if key == "finance":
        return _baidu_topic_mix(
            query=FINANCE_BAIDU_QUERY,
            keywords=FINANCE_KEYWORDS,
            limit=limit,
            timeout=timeout,
            category=key,
        )
    if key == "us-market":
        return _baidu_topic_mix(
            query=US_MARKET_BAIDU_QUERY,
            keywords=US_MARKET_KEYWORDS,
            limit=limit,
            timeout=timeout,
            category=key,
        )
    raise ValueError(f"Unsupported Baidu preset: {key}")


def _merge_item_groups(item_groups: list[list[NewsItem]], limit: int) -> list[NewsItem]:
    seen: set[str] = set()
    merged: list[NewsItem] = []
    max_size = max((len(group) for group in item_groups), default=0)

    for index in range(max_size):
        for group in item_groups:
            if index >= len(group):
                continue

            item = group[index]
            key = normalize_title(item.title)
            if not key or key in seen:
                continue

            seen.add(key)
            merged.append(item)
            if len(merged) >= limit:
                return merged

    return merged


def collect_preset(key: str, source: str, limit: int, timeout: float) -> SectionResult:
    if key not in PRESET_SPECS:
        raise ValueError(f"Unknown preset: {key}")

    spec = PRESET_SPECS[key]
    resolved_sources = list(resolve_sources(spec, source))
    section = SectionResult(
        key=spec.key,
        label=spec.label,
        requested_source=source,
        resolved_sources=resolved_sources,
        generated_at=local_now_string(),
    )

    item_groups: list[list[NewsItem]] = []
    for provider in resolved_sources:
        try:
            if provider == "google":
                item_groups.append(_google_items_for_preset(spec.key, limit=limit, timeout=timeout))
            elif provider == "baidu":
                item_groups.append(_baidu_items_for_preset(spec.key, limit=limit, timeout=timeout))
        except FetchError as exc:
            section.warnings.append(f"{provider} 获取失败: {exc}")

    if len(item_groups) <= 1:
        section.items = dedupe_items(item_groups[0] if item_groups else [], limit=limit)
    else:
        section.items = _merge_item_groups(item_groups, limit=limit)
    if not section.items and not section.warnings:
        section.warnings.append("没有获取到结果。")
    return section


def collect_summary(source: str, limit: int, timeout: float) -> list[SectionResult]:
    return [collect_preset(key, source=source, limit=limit, timeout=timeout) for key in DEFAULT_SUMMARY_PRESETS]


def resolve_search_sources(requested_source: str) -> tuple[str, ...]:
    if requested_source in {"auto", "all"}:
        return ("google", "baidu")
    if requested_source in {"google", "baidu"}:
        return (requested_source,)
    raise ValueError(f"Unsupported source: {requested_source}")


def collect_search(
    query: str,
    source: str,
    limit: int,
    timeout: float,
    google_locale: str,
) -> SectionResult:
    if google_locale == "auto":
        google_locale = "cn" if contains_cjk(query) else "us"

    resolved_sources = list(resolve_search_sources(source))
    section = SectionResult(
        key="search",
        label=f'自定义查询: "{query}"',
        requested_source=source,
        resolved_sources=resolved_sources,
        generated_at=local_now_string(),
    )

    item_groups: list[list[NewsItem]] = []
    for provider in resolved_sources:
        try:
            if provider == "google":
                item_groups.append(
                    fetch_google_news_search(
                        query=query,
                        limit=limit,
                        timeout=timeout,
                        category="search",
                        locale=google_locale,
                    )
                )
            elif provider == "baidu":
                item_groups.append(
                    _baidu_topic_mix(
                        query=query,
                        keywords=(query,),
                        limit=limit,
                        timeout=timeout,
                        category="search",
                    )
                )
        except FetchError as exc:
            section.warnings.append(f"{provider} 获取失败: {exc}")

    if len(item_groups) <= 1:
        section.items = dedupe_items(item_groups[0] if item_groups else [], limit=limit)
    else:
        section.items = _merge_item_groups(item_groups, limit=limit)
    if not section.items and not section.warnings:
        section.warnings.append("没有获取到结果。")
    return section
