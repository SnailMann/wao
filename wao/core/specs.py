from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SourcePlan:
    source: str
    mode: str
    query: str = ""
    locale: str = "us"
    keywords: tuple[str, ...] = ()
    endpoint: str = ""


@dataclass(frozen=True)
class CollectionSpec:
    key: str
    label: str
    description: str
    source_plans: tuple[SourcePlan, ...]
    default_sources: tuple[str, ...]
    default_limit: int
    default_excluded_labels: tuple[str, ...]
    refill_plan: SourcePlan | None = None

    @property
    def supported_sources(self) -> tuple[str, ...]:
        return tuple(dict.fromkeys(plan.source for plan in self.source_plans))


TopicSpec = CollectionSpec
