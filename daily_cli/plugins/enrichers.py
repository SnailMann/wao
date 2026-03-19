from __future__ import annotations

from dataclasses import dataclass

from ..core.models import SectionResult
from ..runtime.body_fetch import BodyFetchError, fetch_item_bodies


@dataclass(frozen=True)
class EnricherPlugin:
    key: str
    label: str
    description: str


ENRICHER_PLUGINS = {
    "body": EnricherPlugin(
        key="body",
        label="Body Fetch",
        description="使用 Playwright 无头浏览器抓取正文。",
    ),
}


def list_enrichers() -> list[EnricherPlugin]:
    return [ENRICHER_PLUGINS[key] for key in ENRICHER_PLUGINS]


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
