from __future__ import annotations

import re

from ..core.models import NewsItem
from .common import FetchError, fetch_text, strip_html


def _extract_anchor_metric(article_html: str, suffix: str) -> str:
    pattern = rf'<a[^>]+href="[^"]*{re.escape(suffix)}"[^>]*>(.*?)</a>'
    match = re.search(pattern, article_html, flags=re.DOTALL)
    if not match:
        return ""
    return strip_html(match.group(1))


def parse_github_trending_html(html_text: str, limit: int, category: str) -> list[NewsItem]:
    articles = re.findall(r'<article class="Box-row">(.*?)</article>', html_text, flags=re.DOTALL)
    if not articles:
        raise FetchError("GitHub Trending page did not contain any repository rows")

    items: list[NewsItem] = []
    for rank, article_html in enumerate(articles, start=1):
        repo_match = re.search(r'<h2[^>]*>.*?<a[^>]+href="(/[^"]+)"', article_html, flags=re.DOTALL)
        if not repo_match:
            continue

        repo_path = repo_match.group(1).strip()
        repo_name = repo_path.strip("/")
        if not repo_name:
            continue

        description_match = re.search(r'<p\b[^>]*>(.*?)</p>', article_html, flags=re.DOTALL)
        language_match = re.search(r'<span itemprop="programmingLanguage">(.*?)</span>', article_html, flags=re.DOTALL)
        stars_today_match = re.search(r'([\d,]+)\s+stars today', article_html)

        items.append(
            NewsItem(
                title=repo_name,
                category=category,
                provider="github",
                feed="GitHub Trending",
                link=f"https://github.com{repo_path}",
                summary=strip_html(description_match.group(1)) if description_match else "",
                publisher="GitHub",
                rank=rank,
                language=strip_html(language_match.group(1)) if language_match else "",
                repo_stars=_extract_anchor_metric(article_html, "/stargazers"),
                repo_forks=_extract_anchor_metric(article_html, "/forks"),
                stars_today=stars_today_match.group(1) if stars_today_match else "",
            )
        )
        if len(items) >= limit:
            break

    if not items:
        raise FetchError("GitHub Trending rows were present but could not be parsed")
    return items


def fetch_github_trending(limit: int, timeout: float, category: str = "github") -> list[NewsItem]:
    best_items: list[NewsItem] = []
    last_error: FetchError | None = None

    for _ in range(3):
        try:
            html_text = fetch_text("https://github.com/trending", timeout=timeout)
            items = parse_github_trending_html(html_text, limit=limit, category=category)
            if len(items) > len(best_items):
                best_items = items
            if len(best_items) >= limit:
                return best_items
        except FetchError as exc:
            last_error = exc

    if best_items:
        return best_items
    if last_error is not None:
        raise last_error
    raise FetchError("GitHub Trending could not be fetched")
