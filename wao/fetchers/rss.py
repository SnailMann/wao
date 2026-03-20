from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha1
from urllib.parse import urlparse
import xml.etree.ElementTree as ET

from ..core.models import NewsItem
from .common import FetchError, fetch_text, format_pub_date, strip_html

DEFAULT_RSSHUB_INSTANCE = "https://rsshub.app"


@dataclass(frozen=True)
class RSSHubRoute:
    uri: str
    route: str
    instance: str

    @property
    def feed_url(self) -> str:
        instance = self.instance.rstrip("/")
        route = self.route if self.route.startswith("/") else f"/{self.route}"
        return f"{instance}{route}"

    @property
    def key(self) -> str:
        digest = sha1(f"{self.instance}|{self.route}".encode("utf-8")).hexdigest()[:8]
        slug = self.route.strip("/").replace("/", "-").replace("?", "-").replace("&", "-")
        slug = slug.strip("-") or "rsshub"
        return f"{slug}-{digest}"


@dataclass(frozen=True)
class FeedUrl:
    uri: str
    url: str

    @property
    def key(self) -> str:
        parsed = urlparse(self.url)
        digest = sha1(self.url.encode("utf-8")).hexdigest()[:8]
        slug = f"{parsed.netloc}{parsed.path}".replace("/", "-")
        slug = slug.strip("-") or "feed"
        return f"{slug}-{digest}"


def default_rsshub_instance() -> str:
    return DEFAULT_RSSHUB_INSTANCE


def normalize_rsshub_instance(value: str | None) -> str:
    instance = (value or DEFAULT_RSSHUB_INSTANCE).strip()
    if not instance:
        raise ValueError("RSSHub 实例地址不能为空")
    if not instance.startswith(("http://", "https://")):
        raise ValueError("RSSHub 实例地址必须以 http:// 或 https:// 开头")
    return instance.rstrip("/")


def parse_rsshub_uri(uri: str, *, instance: str | None = None) -> RSSHubRoute:
    parsed = urlparse(uri)
    if parsed.scheme != "rsshub":
        raise ValueError("RSSHub 订阅地址必须以 rsshub:// 开头")

    parts = []
    if parsed.netloc:
        parts.append(parsed.netloc.strip("/"))
    if parsed.path:
        parts.append(parsed.path.strip("/"))

    route = "/" + "/".join(part for part in parts if part)
    if route == "/":
        raise ValueError("RSSHub 订阅地址缺少有效路由")
    if parsed.query:
        route = f"{route}?{parsed.query}"

    return RSSHubRoute(
        uri=uri,
        route=route,
        instance=normalize_rsshub_instance(instance),
    )


def normalize_feed_url(uri: str) -> str:
    value = uri.strip()
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"}:
        raise ValueError("普通订阅地址必须以 http:// 或 https:// 开头")
    if not parsed.netloc:
        raise ValueError("普通订阅地址缺少有效域名")
    return value


def parse_feed_url(uri: str) -> FeedUrl:
    return FeedUrl(uri=uri, url=normalize_feed_url(uri))


def _local_name(tag: str) -> str:
    if "}" in tag:
        return tag.rsplit("}", 1)[1]
    return tag


def _first_child(node: ET.Element, names: tuple[str, ...]) -> ET.Element | None:
    for child in node:
        if _local_name(child.tag) in names:
            return child
    return None


def _first_child_text(node: ET.Element, names: tuple[str, ...]) -> str:
    child = _first_child(node, names)
    if child is None:
        return ""
    text = "".join(child.itertext()).strip()
    return text


def _atom_entry_link(entry: ET.Element) -> str:
    for child in entry:
        if _local_name(child.tag) != "link":
            continue
        rel = child.attrib.get("rel", "alternate")
        href = child.attrib.get("href", "").strip()
        if href and rel in {"alternate", ""}:
            return href
    return ""


def parse_generic_feed(
    xml_text: str,
    *,
    limit: int,
    category: str,
    provider: str,
    default_feed_name: str,
) -> tuple[str, list[NewsItem]]:
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as exc:
        raise FetchError(f"{default_feed_name} 返回了无效 XML") from exc

    root_name = _local_name(root.tag)
    if root_name == "rss":
        channel = root.find("./channel")
        if channel is None:
            raise FetchError(f"{default_feed_name} 缺少 channel 节点")

        feed_name = _first_child_text(channel, ("title",)) or default_feed_name
        items: list[NewsItem] = []
        for rank, node in enumerate(channel.findall("./item"), start=1):
            title = _first_child_text(node, ("title",))
            if not title:
                continue
            summary = (
                _first_child_text(node, ("description",))
                or _first_child_text(node, ("content", "encoded"))
            )
            items.append(
                NewsItem(
                    title=title,
                    category=category,
                    provider=provider,
                    feed=feed_name,
                    summary=strip_html(summary),
                    publisher=_first_child_text(node, ("author", "creator")),
                    link=_first_child_text(node, ("link",)),
                    published_at=format_pub_date(
                        _first_child_text(node, ("pubDate", "date", "updated"))
                    ),
                    rank=rank,
                )
            )
            if len(items) >= limit:
                break
        return feed_name, items

    if root_name == "feed":
        feed_name = _first_child_text(root, ("title",)) or default_feed_name
        items: list[NewsItem] = []
        entries = [child for child in root if _local_name(child.tag) == "entry"]
        for rank, entry in enumerate(entries, start=1):
            title = _first_child_text(entry, ("title",))
            if not title:
                continue
            author = ""
            author_node = _first_child(entry, ("author",))
            if author_node is not None:
                author = _first_child_text(author_node, ("name",))
            summary = _first_child_text(entry, ("summary", "content"))
            items.append(
                NewsItem(
                    title=title,
                    category=category,
                    provider=provider,
                    feed=feed_name,
                    summary=strip_html(summary),
                    publisher=author,
                    link=_atom_entry_link(entry),
                    published_at=format_pub_date(
                        _first_child_text(entry, ("published", "updated"))
                    ),
                    rank=rank,
                )
            )
            if len(items) >= limit:
                break
        return feed_name, items

    raise FetchError(f"{default_feed_name} 暂不支持该 feed 格式")


def fetch_rsshub_route(
    route: str,
    *,
    instance: str,
    limit: int,
    timeout: float,
    category: str,
) -> list[NewsItem]:
    route_info = RSSHubRoute(
        uri=f"rsshub://{route.lstrip('/')}",
        route=route,
        instance=normalize_rsshub_instance(instance),
    )
    xml_text = fetch_text(route_info.feed_url, timeout=timeout)
    _, items = parse_generic_feed(
        xml_text,
        limit=limit,
        category=category,
        provider="rsshub",
        default_feed_name="RSSHub",
    )
    return items


def fetch_feed_url(
    url: str,
    *,
    limit: int,
    timeout: float,
    category: str,
) -> list[NewsItem]:
    xml_text = fetch_text(normalize_feed_url(url), timeout=timeout)
    _, items = parse_generic_feed(
        xml_text,
        limit=limit,
        category=category,
        provider="feed",
        default_feed_name="Feed",
    )
    return items
