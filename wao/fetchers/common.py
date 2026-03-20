from __future__ import annotations

import json
import re
from datetime import datetime
from email.utils import parsedate_to_datetime
from html import unescape
from http.client import IncompleteRead
from typing import Iterable
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from ..core.models import NewsItem

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/123.0.0.0 Safari/537.36"
    )
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
        try:
            normalized = value.replace("Z", "+00:00")
            dt = datetime.fromisoformat(normalized)
        except (TypeError, ValueError):
            return value
    if dt.tzinfo is None:
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    return dt.astimezone().strftime("%Y-%m-%d %H:%M:%S %Z")


def normalize_title(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip().casefold()


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


def contains_cjk(text: str) -> bool:
    return bool(re.search(r"[\u4e00-\u9fff]", text))


def local_now_string() -> str:
    return datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S %Z")
