from __future__ import annotations

"""Service-level trend capability built on the shared collector."""

from ..core.specs import CollectionSpec, SourcePlan
from .collector import collect_topic_specs

TREND_SOURCE_CHOICES = ("auto", "google", "baidu", "github", "all")

TREND_SPECS = {
    "google": CollectionSpec(
        key="trend-google",
        label="Google Trends",
        description="查看 Google Trends 美国实时热搜。",
        source_plans=(
            SourcePlan(source="google", mode="trends_us"),
        ),
        default_sources=("google",),
        default_limit=10,
        default_excluded_labels=(),
    ),
    "baidu": CollectionSpec(
        key="trend-baidu",
        label="百度热榜",
        description="查看百度实时热榜。",
        source_plans=(
            SourcePlan(source="baidu", mode="hotboard"),
        ),
        default_sources=("baidu",),
        default_limit=10,
        default_excluded_labels=(),
    ),
    "github": CollectionSpec(
        key="trend-github",
        label="GitHub Trending",
        description="查看 GitHub Trending 热门仓库。",
        source_plans=(
            SourcePlan(source="github", mode="trending"),
        ),
        default_sources=("github",),
        default_limit=10,
        default_excluded_labels=(),
    ),
}


def list_trend_specs() -> list[CollectionSpec]:
    return [TREND_SPECS[key] for key in TREND_SPECS]


def resolve_trend_sources(source: str) -> tuple[str, ...]:
    if source in {"auto", "all"}:
        return tuple(TREND_SPECS)
    if source not in TREND_SPECS:
        raise ValueError(f"不支持的 trend 来源: {source}")
    return (source,)


def collect_trends(
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
):
    specs = [TREND_SPECS[key] for key in resolve_trend_sources(source)]
    return collect_topic_specs(
        specs,
        source="auto",
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


__all__ = [
    "TREND_SOURCE_CHOICES",
    "collect_trends",
    "list_trend_specs",
]
