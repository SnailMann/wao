from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(slots=True)
class NewsItem:
    title: str
    category: str
    provider: str
    feed: str
    link: str = ""
    summary: str = ""
    publisher: str = ""
    published_at: str = ""
    rank: int | None = None
    hot_score: str = ""
    approx_traffic: str = ""
    search_query: str = ""
    language: str = ""
    repo_stars: str = ""
    repo_forks: str = ""
    stars_today: str = ""
    content_label: str = ""
    content_label_name: str = ""
    content_label_score: float = 0.0
    tags: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class SectionResult:
    key: str
    label: str
    requested_source: str
    resolved_sources: list[str]
    generated_at: str
    semantic_enabled: bool = False
    semantic_model: str = ""
    filter_enabled: bool = False
    excluded_labels: list[str] = field(default_factory=list)
    filtered_count: int = 0
    items: list[NewsItem] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["items"] = [item.to_dict() for item in self.items]
        return payload
