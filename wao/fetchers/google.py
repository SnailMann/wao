from __future__ import annotations

import xml.etree.ElementTree as ET

from ..core.models import NewsItem
from .common import FetchError, fetch_text, format_pub_date, strip_html

TREND_NS = {"ht": "https://trends.google.com/trending/rss"}
GOOGLE_LOCALES = {
    "us": {"hl": "en-US", "gl": "US", "ceid": "US:en"},
    "cn": {"hl": "zh-CN", "gl": "CN", "ceid": "CN:zh-Hans"},
}


def _element_text(
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
        title = _element_text(node, "title")
        if not title:
            continue

        items.append(
            NewsItem(
                title=title,
                category=category,
                provider="google",
                feed="Google Trends",
                publisher=_element_text(node, "ht:news_item/ht:news_item_source", TREND_NS),
                summary=_element_text(node, "ht:news_item/ht:news_item_title", TREND_NS),
                link=_element_text(node, "ht:news_item/ht:news_item_url", TREND_NS)
                or _element_text(node, "link"),
                published_at=format_pub_date(_element_text(node, "pubDate")),
                rank=rank,
                approx_traffic=_element_text(node, "ht:approx_traffic", TREND_NS),
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
        raw_title = _element_text(node, "title")
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
                summary=strip_html(_element_text(node, "description")),
                link=_element_text(node, "link"),
                published_at=format_pub_date(_element_text(node, "pubDate")),
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
