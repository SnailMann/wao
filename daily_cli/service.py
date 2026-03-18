from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass

from .models import NewsItem, SectionResult
from .semantic import (
    DEFAULT_EXCLUDED_LABELS,
    MODEL_REPO_ID,
    get_semantic_labeler,
)
from .sources import (
    FetchError,
    contains_cjk,
    dedupe_items,
    fetch_baidu_realtime,
    fetch_github_trending,
    fetch_google_news_search,
    fetch_google_trends_us,
    filter_items_by_keywords,
    local_now_string,
    normalize_title,
)

DEFAULT_SUMMARY_PRESETS = ("us-hot", "china-hot", "ai", "finance", "github")

AI_GOOGLE_QUERY = 'AI OR "artificial intelligence" OR OpenAI OR Anthropic OR Gemini OR Nvidia'
FINANCE_GOOGLE_QUERY = (
    '"stock market" OR Nasdaq OR "S&P 500" OR "Dow Jones" OR '
    '"Federal Reserve" OR earnings OR inflation'
)
US_MARKET_GOOGLE_QUERY = '"US stocks" OR "stock market" OR Nasdaq OR "S&P 500" OR "Dow Jones"'

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
    default_limit: int
    default_excluded_labels: tuple[str, ...]


@dataclass
class PreparedSection:
    spec: PresetSpec
    final_limit: int
    section: SectionResult


PRESET_SPECS = {
    "us-hot": PresetSpec(
        key="us-hot",
        label="美国热门事件",
        description="默认使用 Google Trends RSS，适合追踪美国当天热门搜索与事件。",
        supported_sources=("google",),
        default_sources=("google",),
        default_limit=5,
        default_excluded_labels=DEFAULT_EXCLUDED_LABELS,
    ),
    "china-hot": PresetSpec(
        key="china-hot",
        label="中国热门事件",
        description="默认使用百度热榜结构化数据。",
        supported_sources=("baidu",),
        default_sources=("baidu",),
        default_limit=5,
        default_excluded_labels=DEFAULT_EXCLUDED_LABELS,
    ),
    "ai": PresetSpec(
        key="ai",
        label="AI 发展趋势",
        description="聚合 Google News RSS 与百度热榜中的 AI 相关条目。",
        supported_sources=("google", "baidu"),
        default_sources=("google", "baidu"),
        default_limit=5,
        default_excluded_labels=DEFAULT_EXCLUDED_LABELS,
    ),
    "finance": PresetSpec(
        key="finance",
        label="金融热门事件",
        description="聚合 Google News RSS 与百度热榜中的金融类条目。",
        supported_sources=("google", "baidu"),
        default_sources=("google", "baidu"),
        default_limit=5,
        default_excluded_labels=DEFAULT_EXCLUDED_LABELS,
    ),
    "us-market": PresetSpec(
        key="us-market",
        label="美股焦点",
        description="额外预设，聚合 Google News 与百度热榜中的美股相关热点。",
        supported_sources=("google", "baidu"),
        default_sources=("google", "baidu"),
        default_limit=5,
        default_excluded_labels=DEFAULT_EXCLUDED_LABELS,
    ),
    "github": PresetSpec(
        key="github",
        label="GitHub Trending",
        description="获取 GitHub Trending 项目的热门仓库信息。",
        supported_sources=("github",),
        default_sources=("github",),
        default_limit=10,
        default_excluded_labels=DEFAULT_EXCLUDED_LABELS,
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


def _github_items_for_preset(key: str, limit: int, timeout: float) -> list[NewsItem]:
    if key == "github":
        return fetch_github_trending(limit=limit, timeout=timeout, category=key)
    raise ValueError(f"Unsupported GitHub preset: {key}")


def _baidu_topic_mix(
    keywords: tuple[str, ...],
    limit: int,
    timeout: float,
    category: str,
) -> list[NewsItem]:
    hot_items = fetch_baidu_realtime(limit=max(limit * 4, 20), timeout=timeout, category=category)
    return filter_items_by_keywords(hot_items, keywords=keywords, limit=limit, category=category)


def _baidu_items_for_preset(key: str, limit: int, timeout: float) -> list[NewsItem]:
    if key == "china-hot":
        return fetch_baidu_realtime(limit=limit, timeout=timeout, category=key)
    if key == "ai":
        return _baidu_topic_mix(
            keywords=AI_KEYWORDS,
            limit=limit,
            timeout=timeout,
            category=key,
        )
    if key == "finance":
        return _baidu_topic_mix(
            keywords=FINANCE_KEYWORDS,
            limit=limit,
            timeout=timeout,
            category=key,
        )
    if key == "us-market":
        return _baidu_topic_mix(
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


def _candidate_limit(final_limit: int, semantic_filter: bool) -> int:
    if not semantic_filter:
        return final_limit
    return max(final_limit * 3, final_limit + 8)


def _fetch_provider_items(provider: str, key: str, limit: int, timeout: float) -> list[NewsItem]:
    if provider == "google":
        return _google_items_for_preset(key, limit=limit, timeout=timeout)
    if provider == "baidu":
        return _baidu_items_for_preset(key, limit=limit, timeout=timeout)
    if provider == "github":
        return _github_items_for_preset(key, limit=limit, timeout=timeout)
    raise ValueError(f"Unsupported provider: {provider}")


def _collect_provider_groups(
    key: str,
    resolved_sources: list[str],
    fetch_limit: int,
    timeout: float,
) -> tuple[list[list[NewsItem]], list[str]]:
    item_groups: list[list[NewsItem]] = []
    warnings: list[str] = []

    if len(resolved_sources) <= 1:
        for provider in resolved_sources:
            try:
                item_groups.append(_fetch_provider_items(provider, key=key, limit=fetch_limit, timeout=timeout))
            except FetchError as exc:
                warnings.append(f"{provider} 获取失败: {exc}")
        return item_groups, warnings

    with ThreadPoolExecutor(max_workers=min(4, len(resolved_sources))) as executor:
        futures = {
            provider: executor.submit(_fetch_provider_items, provider, key, fetch_limit, timeout)
            for provider in resolved_sources
        }
        for provider in resolved_sources:
            try:
                item_groups.append(futures[provider].result())
            except FetchError as exc:
                warnings.append(f"{provider} 获取失败: {exc}")

    return item_groups, warnings


def _prepare_section(
    key: str,
    source: str,
    limit: int | None,
    timeout: float,
    semantic_enabled: bool,
    semantic_filter: bool,
) -> PreparedSection:
    if key not in PRESET_SPECS:
        raise ValueError(f"Unknown preset: {key}")

    spec = PRESET_SPECS[key]
    final_limit = spec.default_limit if limit is None else limit
    fetch_limit = _candidate_limit(final_limit, semantic_filter and semantic_enabled)
    resolved_sources = list(resolve_sources(spec, source))
    section = SectionResult(
        key=spec.key,
        label=spec.label,
        requested_source=source,
        resolved_sources=resolved_sources,
        generated_at=local_now_string(),
    )

    item_groups, warnings = _collect_provider_groups(spec.key, resolved_sources, fetch_limit, timeout)
    section.warnings.extend(warnings)

    if len(item_groups) <= 1:
        section.items = dedupe_items(item_groups[0] if item_groups else [], limit=fetch_limit)
    else:
        section.items = _merge_item_groups(item_groups, limit=fetch_limit)

    if spec.key == "github" and section.items and len(section.items) < final_limit:
        section.warnings.append(
            f"GitHub Trending 当前只解析到 {len(section.items)} 条结果，少于目标 {final_limit} 条。"
        )

    return PreparedSection(spec=spec, final_limit=final_limit, section=section)


def _annotate_prepared_sections(prepared_sections: list[PreparedSection], semantic_model_dir: str | None) -> None:
    all_items = [item for prepared in prepared_sections for item in prepared.section.items]
    if not all_items:
        return

    labeler = get_semantic_labeler(semantic_model_dir)
    labeler.annotate_items(all_items)


def _finalize_section(
    prepared: PreparedSection,
    section: SectionResult,
    semantic_enabled: bool,
    semantic_filter: bool,
    excluded_labels: tuple[str, ...] | None,
) -> SectionResult:
    default_excluded_labels = prepared.spec.default_excluded_labels
    final_limit = prepared.final_limit

    if not semantic_enabled:
        if len(section.items) > final_limit:
            section.items = section.items[:final_limit]
        if not section.items and not section.warnings:
            section.warnings.append("没有获取到结果。")
        return section

    section.semantic_enabled = True
    section.semantic_model = MODEL_REPO_ID

    if semantic_filter:
        blocked = excluded_labels if excluded_labels else default_excluded_labels
        section.filter_enabled = True
        section.excluded_labels = list(blocked)

        kept: list[NewsItem] = []
        filtered_count = 0
        for item in section.items:
            if item.content_label and item.content_label in blocked:
                filtered_count += 1
                continue
            kept.append(item)

        section.items = kept
        section.filtered_count = filtered_count

        if filtered_count and not section.items and not section.warnings:
            section.warnings.append("语义过滤后没有保留结果。")

    if len(section.items) > final_limit:
        section.items = section.items[:final_limit]
    if not section.items and not section.warnings:
        section.warnings.append("没有获取到结果。")
    return section


def collect_presets(
    keys: list[str] | tuple[str, ...],
    source: str,
    limit: int | None,
    timeout: float,
    semantic_enabled: bool = True,
    semantic_filter: bool = True,
    excluded_labels: tuple[str, ...] | None = None,
    semantic_model_dir: str | None = None,
) -> list[SectionResult]:
    if not keys:
        return []

    if len(keys) == 1:
        prepared_sections = [
            _prepare_section(
                keys[0],
                source=source,
                limit=limit,
                timeout=timeout,
                semantic_enabled=semantic_enabled,
                semantic_filter=semantic_filter,
            )
        ]
    else:
        with ThreadPoolExecutor(max_workers=min(8, len(keys))) as executor:
            futures = [
                executor.submit(
                    _prepare_section,
                    key,
                    source,
                    limit,
                    timeout,
                    semantic_enabled,
                    semantic_filter,
                )
                for key in keys
            ]
            prepared_sections = [future.result() for future in futures]

    if semantic_enabled:
        _annotate_prepared_sections(prepared_sections, semantic_model_dir=semantic_model_dir)

    return [
        _finalize_section(
            prepared,
            prepared.section,
            semantic_enabled=semantic_enabled,
            semantic_filter=semantic_filter,
            excluded_labels=excluded_labels,
        )
        for prepared in prepared_sections
    ]


def collect_preset(
    key: str,
    source: str,
    limit: int | None,
    timeout: float,
    semantic_enabled: bool = True,
    semantic_filter: bool = True,
    excluded_labels: tuple[str, ...] | None = None,
    semantic_model_dir: str | None = None,
) -> SectionResult:
    return collect_presets(
        [key],
        source=source,
        limit=limit,
        timeout=timeout,
        semantic_enabled=semantic_enabled,
        semantic_filter=semantic_filter,
        excluded_labels=excluded_labels,
        semantic_model_dir=semantic_model_dir,
    )[0]


def collect_summary(
    source: str,
    limit: int | None,
    timeout: float,
    semantic_enabled: bool = True,
    semantic_filter: bool = True,
    excluded_labels: tuple[str, ...] | None = None,
    semantic_model_dir: str | None = None,
) -> list[SectionResult]:
    return collect_presets(
        list(DEFAULT_SUMMARY_PRESETS),
        source=source,
        limit=limit,
        timeout=timeout,
        semantic_enabled=semantic_enabled,
        semantic_filter=semantic_filter,
        excluded_labels=excluded_labels,
        semantic_model_dir=semantic_model_dir,
    )


def collect_search(
    query: str,
    limit: int,
    timeout: float,
    google_locale: str,
    semantic_enabled: bool = True,
    semantic_filter: bool = True,
    excluded_labels: tuple[str, ...] | None = None,
    semantic_model_dir: str | None = None,
) -> SectionResult:
    if google_locale == "auto":
        google_locale = "cn" if contains_cjk(query) else "us"

    fetch_limit = _candidate_limit(limit, semantic_filter and semantic_enabled)
    section = SectionResult(
        key="search",
        label=f'自定义查询: "{query}"',
        requested_source="google",
        resolved_sources=["google"],
        generated_at=local_now_string(),
    )

    try:
        section.items = dedupe_items(
            fetch_google_news_search(
                query=query,
                limit=fetch_limit,
                timeout=timeout,
                category="search",
                locale=google_locale,
            ),
            limit=fetch_limit,
        )
    except FetchError as exc:
        section.warnings.append(f"google 获取失败: {exc}")

    prepared = PreparedSection(
        spec=PresetSpec(
            key="search",
            label="search",
            description="按用户查询进行 Google News 检索。",
            supported_sources=("google",),
            default_sources=("google",),
            default_limit=limit,
            default_excluded_labels=DEFAULT_EXCLUDED_LABELS,
        ),
        final_limit=limit,
        section=section,
    )

    if semantic_enabled:
        _annotate_prepared_sections([prepared], semantic_model_dir=semantic_model_dir)

    return _finalize_section(
        prepared,
        section,
        semantic_enabled=semantic_enabled,
        semantic_filter=semantic_filter,
        excluded_labels=excluded_labels,
    )
