from __future__ import annotations

import json
import re
from dataclasses import replace
from datetime import datetime
from email.utils import parsedate_to_datetime
from html import unescape
from http.client import IncompleteRead
from typing import Iterable
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen
import xml.etree.ElementTree as ET

from ..core.models import NewsItem

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/123.0.0.0 Safari/537.36"
    )
}

TREND_NS = {"ht": "https://trends.google.com/trending/rss"}
GOOGLE_LOCALES = {
    "us": {"hl": "en-US", "gl": "US", "ceid": "US:en"},
    "cn": {"hl": "zh-CN", "gl": "CN", "ceid": "CN:zh-Hans"},
}


class FetchError(RuntimeError):
    """Raised when an upstream source cannot be fetched or parsed."""


def _build_url(url: str, params: dict[str, str] | None = None) -> str:
    if not params:
        return url
    return f"{url}?{urlencode(params)}"


def fetch_text(
    url: str,
    params: dict[str, str] | None = None,
    headers: dict[str, str] | None = None,
    timeout: float = 10.0,
) -> str:
    request_headers = dict(DEFAULT_HEADERS)
    if headers:
        request_headers.update(headers)
    request = Request(_build_url(url, params), headers=request_headers)
    try:
        with urlopen(request, timeout=timeout) as response:
            charset = response.headers.get_content_charset() or "utf-8"
            try:
                payload = response.read()
            except IncompleteRead as exc:
                payload = exc.partial
            return payload.decode(charset, errors="replace")
    except HTTPError as exc:
        raise FetchError(f"{url} returned HTTP {exc.code}") from exc
    except URLError as exc:
        raise FetchError(f"{url} is unavailable: {exc.reason}") from exc
    except TimeoutError as exc:
        raise FetchError(f"{url} timed out after {timeout}s") from exc


def fetch_json(
    url: str,
    params: dict[str, str] | None = None,
    headers: dict[str, str] | None = None,
    timeout: float = 10.0,
) -> dict:
    text = fetch_text(url, params=params, headers=headers, timeout=timeout)
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise FetchError(f"{url} returned invalid JSON") from exc


def strip_html(value: str) -> str:
    cleaned = re.sub(r"<[^>]+>", " ", value or "")
    cleaned = unescape(cleaned)
    return re.sub(r"\s+", " ", cleaned).strip()


def format_pub_date(value: str) -> str:
    if not value:
        return ""
    try:
        dt = parsedate_to_datetime(value)
    except (TypeError, ValueError):
        return value
    if dt.tzinfo is None:
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    return dt.astimezone().strftime("%Y-%m-%d %H:%M:%S %Z")


def normalize_title(value: str) -> str:
    normalized = re.sub(r"\s+", " ", value or "").strip().casefold()
    return normalized


def dedupe_items(items: Iterable[NewsItem], limit: int | None = None) -> list[NewsItem]:
    seen: set[str] = set()
    deduped: list[NewsItem] = []
    for item in items:
        key = normalize_title(item.title)
        if not key or key in seen:
            continue
        seen.add(key)
        deduped.append(item)
        if limit is not None and len(deduped) >= limit:
            break
    return deduped


def element_text(
    node: ET.Element,
    path: str,
    namespaces: dict[str, str] | None = None,
) -> str:
    child = node.find(path, namespaces or {})
    if child is None or child.text is None:
        return ""
    return child.text.strip()


def parse_google_trends_rss(xml_text: str, limit: int, category: str) -> list[NewsItem]:
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as exc:
        raise FetchError("Google Trends RSS returned invalid XML") from exc

    items: list[NewsItem] = []
    for rank, node in enumerate(root.findall("./channel/item"), start=1):
        title = element_text(node, "title")
        if not title:
            continue

        related_title = element_text(node, "ht:news_item/ht:news_item_title", TREND_NS)
        related_source = element_text(node, "ht:news_item/ht:news_item_source", TREND_NS)
        related_url = element_text(node, "ht:news_item/ht:news_item_url", TREND_NS)
        approx_traffic = element_text(node, "ht:approx_traffic", TREND_NS)
        published_at = format_pub_date(element_text(node, "pubDate"))

        items.append(
            NewsItem(
                title=title,
                category=category,
                provider="google",
                feed="Google Trends",
                publisher=related_source,
                summary=related_title,
                link=related_url or element_text(node, "link"),
                published_at=published_at,
                rank=rank,
                approx_traffic=approx_traffic,
            )
        )

        if len(items) >= limit:
            break

    return items


def fetch_google_trends_us(limit: int, timeout: float, category: str = "us-hot") -> list[NewsItem]:
    xml_text = fetch_text("https://trends.google.com/trending/rss", params={"geo": "US"}, timeout=timeout)
    return parse_google_trends_rss(xml_text, limit=limit, category=category)


def _split_google_news_title(raw_title: str) -> tuple[str, str]:
    if " - " not in raw_title:
        return raw_title, ""
    title, publisher = raw_title.rsplit(" - ", 1)
    return title.strip(), publisher.strip()


def parse_google_news_rss(xml_text: str, limit: int, category: str) -> list[NewsItem]:
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as exc:
        raise FetchError("Google News RSS returned invalid XML") from exc

    items: list[NewsItem] = []
    for rank, node in enumerate(root.findall("./channel/item"), start=1):
        raw_title = element_text(node, "title")
        title, publisher = _split_google_news_title(raw_title)
        if not title:
            continue

        items.append(
            NewsItem(
                title=title,
                category=category,
                provider="google",
                feed="Google News",
                publisher=publisher,
                summary=strip_html(element_text(node, "description")),
                link=element_text(node, "link"),
                published_at=format_pub_date(element_text(node, "pubDate")),
                rank=rank,
            )
        )

        if len(items) >= limit:
            break

    return items


def fetch_google_news_search(
    query: str,
    limit: int,
    timeout: float,
    category: str,
    locale: str = "us",
) -> list[NewsItem]:
    locale_config = GOOGLE_LOCALES.get(locale, GOOGLE_LOCALES["us"])
    params = {
        "q": query,
        "hl": locale_config["hl"],
        "gl": locale_config["gl"],
        "ceid": locale_config["ceid"],
    }
    xml_text = fetch_text("https://news.google.com/rss/search", params=params, timeout=timeout)
    return parse_google_news_rss(xml_text, limit=limit, category=category)


def fetch_google_news_top(
    limit: int,
    timeout: float,
    category: str,
    locale: str = "us",
) -> list[NewsItem]:
    locale_config = GOOGLE_LOCALES.get(locale, GOOGLE_LOCALES["us"])
    params = {
        "hl": locale_config["hl"],
        "gl": locale_config["gl"],
        "ceid": locale_config["ceid"],
    }
    xml_text = fetch_text("https://news.google.com/rss", params=params, timeout=timeout)
    return parse_google_news_rss(xml_text, limit=limit, category=category)


def _extract_anchor_metric(article_html: str, suffix: str) -> str:
    pattern = rf'<a[^>]+href="[^"]*{re.escape(suffix)}"[^>]*>(.*?)</a>'
    match = re.search(pattern, article_html, flags=re.DOTALL)
    if not match:
        return ""
    metric = strip_html(match.group(1))
    return metric


def parse_github_trending_html(html_text: str, limit: int, category: str) -> list[NewsItem]:
    articles = re.findall(r'<article class="Box-row">(.*?)</article>', html_text, flags=re.DOTALL)
    if not articles:
        raise FetchError("GitHub Trending page did not contain any repository rows")

    items: list[NewsItem] = []
    for rank, article_html in enumerate(articles, start=1):
        repo_match = re.search(
            r'<h2[^>]*>.*?<a[^>]+href="(/[^"]+)"',
            article_html,
            flags=re.DOTALL,
        )
        if not repo_match:
            continue

        repo_path = repo_match.group(1).strip()
        repo_name = repo_path.strip("/")
        if not repo_name:
            continue

        description_match = re.search(r'<p\b[^>]*>(.*?)</p>', article_html, flags=re.DOTALL)
        description = strip_html(description_match.group(1)) if description_match else ""

        language_match = re.search(
            r'<span itemprop="programmingLanguage">(.*?)</span>',
            article_html,
            flags=re.DOTALL,
        )
        language = strip_html(language_match.group(1)) if language_match else ""

        total_stars = _extract_anchor_metric(article_html, "/stargazers")
        total_forks = _extract_anchor_metric(article_html, "/forks")

        stars_today_match = re.search(r'([\d,]+)\s+stars today', article_html)
        stars_today = stars_today_match.group(1) if stars_today_match else ""

        items.append(
            NewsItem(
                title=repo_name,
                category=category,
                provider="github",
                feed="GitHub Trending",
                link=f"https://github.com{repo_path}",
                summary=description,
                publisher="GitHub",
                rank=rank,
                language=language,
                repo_stars=total_stars,
                repo_forks=total_forks,
                stars_today=stars_today,
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


def contains_cjk(text: str) -> bool:
    return bool(re.search(r"[\u4e00-\u9fff]", text))


def local_now_string() -> str:
    return datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S %Z")
