from __future__ import annotations

import json
import re
from dataclasses import replace
from typing import Iterable

from ..core.models import NewsItem
from .common import FetchError, fetch_text


def parse_baidu_realtime_html(html_text: str, limit: int, category: str) -> list[NewsItem]:
    match = re.search(r"<!--s-data:(\{.*?\})-->", html_text, flags=re.DOTALL)
    if not match:
        raise FetchError("Baidu realtime page is missing structured hotboard data")

    try:
        payload = json.loads(match.group(1))
    except json.JSONDecodeError as exc:
        raise FetchError("Baidu realtime hotboard data is invalid JSON") from exc

    cards = payload.get("data", {}).get("cards", [])
    hot_list = next((card.get("content", []) for card in cards if card.get("component") == "hotList"), [])
    if not hot_list:
        raise FetchError("Baidu realtime hotboard is empty")

    items: list[NewsItem] = []
    for rank, entry in enumerate(hot_list, start=1):
        title = str(entry.get("word") or entry.get("query") or "").strip()
        if not title:
            continue

        tags: list[str] = []
        if entry.get("isTop"):
            tags.append("置顶")
        hot_change = str(entry.get("hotChange") or "").strip()
        if hot_change and hot_change not in {"same", "0"}:
            tags.append(hot_change)

        items.append(
            NewsItem(
                title=title,
                category=category,
                provider="baidu",
                feed="Baidu Hotboard",
                publisher="百度热搜",
                summary=str(entry.get("desc") or "").strip(),
                link=str(entry.get("url") or entry.get("appUrl") or "").strip(),
                rank=rank,
                hot_score=str(entry.get("hotScore") or "").strip(),
                tags=tags,
            )
        )
        if len(items) >= limit:
            break
    return items


def fetch_baidu_realtime(limit: int, timeout: float, category: str = "china-hot") -> list[NewsItem]:
    html_text = fetch_text("https://top.baidu.com/board", params={"tab": "realtime"}, timeout=timeout)
    return parse_baidu_realtime_html(html_text, limit=limit, category=category)


def filter_items_by_keywords(
    items: Iterable[NewsItem],
    keywords: Iterable[str],
    limit: int,
    category: str,
) -> list[NewsItem]:
    normalized_keywords = [keyword.casefold() for keyword in keywords if keyword]
    scored: list[tuple[int, NewsItem]] = []
    for item in items:
        haystack = f"{item.title} {item.summary}".casefold()
        score = sum(1 for keyword in normalized_keywords if keyword in haystack)
        if score <= 0:
            continue
        scored.append((score, replace(item, category=category)))

    scored.sort(key=lambda pair: (-pair[0], pair[1].rank or 9999))
    return [item for _, item in scored[:limit]]
