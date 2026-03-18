from __future__ import annotations

import json

from .models import SectionResult


def _shorten(value: str, limit: int = 160) -> str:
    value = (value or "").strip()
    if len(value) <= limit:
        return value
    return value[: limit - 3].rstrip() + "..."


def render_text(sections: list[SectionResult]) -> str:
    lines: list[str] = []
    if sections:
        lines.append(f"生成时间: {sections[0].generated_at}")

    for section in sections:
        lines.append("")
        lines.append(f"{section.label} [{section.key}]")
        lines.append(f"来源: {', '.join(section.resolved_sources)}")
        if section.semantic_enabled:
            semantic_parts = [f"语义标签: 开启", f"模型 {section.semantic_model}"]
            if section.filter_enabled:
                labels = ", ".join(section.excluded_labels) if section.excluded_labels else "无"
                semantic_parts.append(f"过滤标签 {labels}")
                semantic_parts.append(f"过滤 {section.filtered_count} 条")
            lines.append(" | ".join(semantic_parts))

        for warning in section.warnings:
            lines.append(f"注意: {warning}")

        if not section.items:
            lines.append("暂无结果")
            continue

        for index, item in enumerate(section.items, start=1):
            lines.append(f"{index}. {item.title}")

            meta_parts = [item.feed]
            if item.publisher:
                meta_parts.append(item.publisher)
            if item.approx_traffic:
                meta_parts.append(f"热度 {item.approx_traffic}")
            if item.hot_score:
                meta_parts.append(f"热搜值 {item.hot_score}")
            if item.language:
                meta_parts.append(item.language)
            if item.repo_stars:
                meta_parts.append(f"Stars {item.repo_stars}")
            if item.repo_forks:
                meta_parts.append(f"Forks {item.repo_forks}")
            if item.stars_today:
                meta_parts.append(f"Today +{item.stars_today}")
            if item.published_at:
                meta_parts.append(item.published_at)
            if item.content_label_name:
                if item.content_label_score:
                    meta_parts.append(f"语义 {item.content_label_name} {item.content_label_score:.2f}")
                else:
                    meta_parts.append(f"语义 {item.content_label_name}")
            if item.tags:
                meta_parts.append("标签 " + "/".join(item.tags))

            lines.append("   " + " | ".join(meta_parts))

            if item.summary:
                lines.append("   " + _shorten(item.summary))
            if item.link:
                lines.append("   " + item.link)

    return "\n".join(lines).strip() + "\n"


def render_json(sections: list[SectionResult]) -> str:
    payload = {
        "generated_at": sections[0].generated_at if sections else "",
        "sections": [section.to_dict() for section in sections],
    }
    return json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
