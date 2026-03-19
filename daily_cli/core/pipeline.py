from __future__ import annotations

from dataclasses import dataclass

from ..plugins.enrichers import enrich_sections_with_body
from ..plugins.filters import annotate_items, get_filter_plugin
from ..plugins.providers import dedupe_source_items, fetch_source_plan
from ..runtime.sources import FetchError, contains_cjk, local_now_string, normalize_title
from .models import NewsItem, SectionResult
from .topics import (
    DEFAULT_SUMMARY_TOPICS,
    TopicSpec,
    build_search_topic,
    get_source_plan,
    get_topic,
    resolve_sources,
)


@dataclass
class PreparedTopic:
    spec: TopicSpec
    final_limit: int
    blocked_labels: tuple[str, ...]
    filter_active: bool
    section: SectionResult


def _merge_source_groups(item_groups: list[list[NewsItem]], limit: int) -> list[NewsItem]:
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


def _candidate_limit(final_limit: int, filter_active: bool) -> int:
    if not filter_active:
        return final_limit
    return max(final_limit * 3, final_limit + 8)


def _collect_source_groups(
    spec: TopicSpec,
    resolved_sources: list[str],
    fetch_limit: int,
    timeout: float,
) -> tuple[list[list[NewsItem]], list[str]]:
    item_groups: list[list[NewsItem]] = []
    warnings: list[str] = []

    for source_key in resolved_sources:
        plan = get_source_plan(spec, source_key)
        try:
            item_groups.append(
                fetch_source_plan(
                    plan,
                    topic_key=spec.key,
                    limit=fetch_limit,
                    timeout=timeout,
                )
            )
        except FetchError as exc:
            warnings.append(f"{source_key} 获取失败: {exc}")

    return item_groups, warnings


def _prepare_topic(
    spec: TopicSpec,
    *,
    source: str,
    limit: int | None,
    timeout: float,
    semantic_enabled: bool,
    semantic_filter: bool,
    excluded_labels: tuple[str, ...] | None,
) -> PreparedTopic:
    final_limit = spec.default_limit if limit is None else limit
    effective_excluded_labels = excluded_labels if excluded_labels is not None else spec.default_excluded_labels
    filter_active = semantic_enabled and semantic_filter and bool(effective_excluded_labels)
    fetch_limit = _candidate_limit(final_limit, filter_active)
    resolved_sources = list(resolve_sources(spec, source))
    section = SectionResult(
        key=spec.key,
        label=spec.label,
        requested_source=source,
        resolved_sources=resolved_sources,
        generated_at=local_now_string(),
    )

    item_groups, warnings = _collect_source_groups(spec, resolved_sources, fetch_limit, timeout)
    section.warnings.extend(warnings)

    if len(item_groups) <= 1:
        section.items = dedupe_source_items(item_groups[0] if item_groups else [], limit=fetch_limit)
    else:
        section.items = _merge_source_groups(item_groups, limit=fetch_limit)

    if spec.key == "github" and section.items and len(section.items) < final_limit:
        section.warnings.append(
            f"GitHub Trending 当前只解析到 {len(section.items)} 条结果，少于目标 {final_limit} 条。"
        )

    return PreparedTopic(
        spec=spec,
        final_limit=final_limit,
        blocked_labels=effective_excluded_labels,
        filter_active=filter_active,
        section=section,
    )


def _annotate_prepared_topics(
    prepared_topics: list[PreparedTopic],
    *,
    semantic_model_dir: str | None,
    filter_mode: str,
) -> None:
    all_items = [
        item
        for prepared in prepared_topics
        if prepared.filter_active
        for item in prepared.section.items
    ]
    if not all_items:
        return

    annotate_items(
        all_items,
        filter_mode=filter_mode,
        semantic_model_dir=semantic_model_dir,
    )


def _refill_topic_results(
    prepared: PreparedTopic,
    section: SectionResult,
    *,
    seen_titles: set[str],
    timeout: float,
    semantic_model_dir: str | None,
    filter_mode: str,
) -> bool:
    refill_plan = prepared.spec.refill_plan
    missing = prepared.final_limit - len(section.items)
    if refill_plan is None or missing <= 0:
        return False

    refill_limit = _candidate_limit(missing, True)
    try:
        refill_items = dedupe_source_items(
            fetch_source_plan(
                refill_plan,
                topic_key=prepared.spec.key,
                limit=refill_limit,
                timeout=timeout,
            ),
            limit=refill_limit,
        )
    except FetchError as exc:
        section.warnings.append(f"{refill_plan.source} 回补失败: {exc}")
        return True

    unique_refill: list[NewsItem] = []
    for item in refill_items:
        normalized = normalize_title(item.title)
        if not normalized or normalized in seen_titles:
            continue
        seen_titles.add(normalized)
        unique_refill.append(item)

    if not unique_refill:
        return True

    annotate_items(
        unique_refill,
        filter_mode=filter_mode,
        semantic_model_dir=semantic_model_dir,
    )

    for item in unique_refill:
        if item.content_label and item.content_label in prepared.blocked_labels:
            section.filtered_count += 1
            continue
        section.items.append(item)
        if len(section.items) >= prepared.final_limit:
            break

    return True


def _finalize_topic_section(
    prepared: PreparedTopic,
    section: SectionResult,
    *,
    timeout: float,
    semantic_model_dir: str | None,
    filter_mode: str,
) -> SectionResult:
    final_limit = prepared.final_limit

    if not prepared.filter_active:
        if len(section.items) > final_limit:
            section.items = section.items[:final_limit]
        if not section.items and not section.warnings:
            section.warnings.append("没有获取到结果。")
        return section

    plugin = get_filter_plugin(filter_mode)
    section.semantic_enabled = True
    section.semantic_model = plugin.model_name
    section.filter_enabled = True
    section.excluded_labels = list(prepared.blocked_labels)

    kept: list[NewsItem] = []
    filtered_count = 0
    for item in section.items:
        if item.content_label and item.content_label in prepared.blocked_labels:
            filtered_count += 1
            continue
        kept.append(item)

    section.items = kept
    section.filtered_count = filtered_count

    seen_titles = {normalize_title(item.title) for item in section.items if normalize_title(item.title)}
    refill_attempted = _refill_topic_results(
        prepared,
        section,
        seen_titles=seen_titles,
        timeout=timeout,
        semantic_model_dir=semantic_model_dir,
        filter_mode=filter_mode,
    )

    if filtered_count and not section.items and not section.warnings:
        section.warnings.append("语义过滤后没有保留结果。")
    if len(section.items) > final_limit:
        section.items = section.items[:final_limit]
    if (
        refill_attempted
        and len(section.items) < final_limit
        and not any("回补" in warning for warning in section.warnings)
    ):
        section.warnings.append(
            f"语义过滤后仅保留 {len(section.items)} 条，已尝试使用 {prepared.spec.refill_plan.source} 回补。"
        )
    if not section.items and not section.warnings:
        section.warnings.append("没有获取到结果。")
    return section


def collect_topics(
    keys: list[str] | tuple[str, ...],
    *,
    source: str,
    limit: int | None,
    timeout: float,
    semantic_enabled: bool = True,
    semantic_filter: bool = True,
    excluded_labels: tuple[str, ...] | None = None,
    semantic_model_dir: str | None = None,
    filter_mode: str = "tfidf",
    fetch_body: bool = False,
    body_timeout: float = 15.0,
    body_max_chars: int = 4000,
) -> list[SectionResult]:
    if not keys:
        return []

    prepared_topics = [
        _prepare_topic(
            get_topic(key),
            source=source,
            limit=limit,
            timeout=timeout,
            semantic_enabled=semantic_enabled,
            semantic_filter=semantic_filter,
            excluded_labels=excluded_labels,
        )
        for key in keys
    ]

    if semantic_enabled:
        _annotate_prepared_topics(
            prepared_topics,
            semantic_model_dir=semantic_model_dir,
            filter_mode=filter_mode,
        )

    sections = [
        _finalize_topic_section(
            prepared,
            prepared.section,
            timeout=timeout,
            semantic_model_dir=semantic_model_dir,
            filter_mode=filter_mode,
        )
        for prepared in prepared_topics
    ]

    if fetch_body:
        enrich_sections_with_body(
            sections,
            timeout=body_timeout,
            max_chars=body_max_chars,
        )
    return sections


def collect_topic(
    key: str,
    *,
    source: str,
    limit: int | None,
    timeout: float,
    semantic_enabled: bool = True,
    semantic_filter: bool = True,
    excluded_labels: tuple[str, ...] | None = None,
    semantic_model_dir: str | None = None,
    filter_mode: str = "tfidf",
    fetch_body: bool = False,
    body_timeout: float = 15.0,
    body_max_chars: int = 4000,
) -> SectionResult:
    return collect_topics(
        [key],
        source=source,
        limit=limit,
        timeout=timeout,
        semantic_enabled=semantic_enabled,
        semantic_filter=semantic_filter,
        excluded_labels=excluded_labels,
        semantic_model_dir=semantic_model_dir,
        filter_mode=filter_mode,
        fetch_body=fetch_body,
        body_timeout=body_timeout,
        body_max_chars=body_max_chars,
    )[0]


def collect_summary(
    *,
    source: str,
    limit: int | None,
    timeout: float,
    semantic_enabled: bool = True,
    semantic_filter: bool = True,
    excluded_labels: tuple[str, ...] | None = None,
    semantic_model_dir: str | None = None,
    filter_mode: str = "tfidf",
    fetch_body: bool = False,
    body_timeout: float = 15.0,
    body_max_chars: int = 4000,
) -> list[SectionResult]:
    return collect_topics(
        list(DEFAULT_SUMMARY_TOPICS),
        source=source,
        limit=limit,
        timeout=timeout,
        semantic_enabled=semantic_enabled,
        semantic_filter=semantic_filter,
        excluded_labels=excluded_labels,
        semantic_model_dir=semantic_model_dir,
        filter_mode=filter_mode,
        fetch_body=fetch_body,
        body_timeout=body_timeout,
        body_max_chars=body_max_chars,
    )


def collect_search(
    *,
    query: str,
    limit: int,
    timeout: float,
    google_locale: str,
    semantic_enabled: bool = True,
    semantic_filter: bool = True,
    excluded_labels: tuple[str, ...] | None = None,
    semantic_model_dir: str | None = None,
    filter_mode: str = "tfidf",
    fetch_body: bool = False,
    body_timeout: float = 15.0,
    body_max_chars: int = 4000,
) -> SectionResult:
    resolved_locale = google_locale
    if resolved_locale == "auto":
        resolved_locale = "cn" if contains_cjk(query) else "us"

    prepared = _prepare_topic(
        build_search_topic(query, resolved_locale),
        source="google",
        limit=limit,
        timeout=timeout,
        semantic_enabled=semantic_enabled,
        semantic_filter=semantic_filter,
        excluded_labels=excluded_labels,
    )

    if semantic_enabled:
        _annotate_prepared_topics(
            [prepared],
            semantic_model_dir=semantic_model_dir,
            filter_mode=filter_mode,
        )

    section = _finalize_topic_section(
        prepared,
        prepared.section,
        timeout=timeout,
        semantic_model_dir=semantic_model_dir,
        filter_mode=filter_mode,
    )

    if fetch_body:
        enrich_sections_with_body(
            [section],
            timeout=body_timeout,
            max_chars=body_max_chars,
        )

    return section
