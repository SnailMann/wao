from __future__ import annotations

import json
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from ..core.models import NewsItem
from ..core.x_auth import resolve_x_bearer_token
from .sources import DEFAULT_HEADERS, FetchError, format_pub_date

X_API_BASE = "https://api.x.com/2"


def _x_headers() -> dict[str, str]:
    token_state = resolve_x_bearer_token()
    headers = dict(DEFAULT_HEADERS)
    headers["Authorization"] = f"Bearer {token_state.token}"
    return headers


def _decode_x_error(exc: HTTPError, endpoint: str) -> FetchError:
    body = exc.read().decode("utf-8", errors="replace")
    detail = ""
    title = ""
    try:
        payload = json.loads(body)
        detail = str(payload.get("detail") or "")
        title = str(payload.get("title") or "")
    except json.JSONDecodeError:
        detail = body.strip()

    if exc.code == 402 and title == "CreditsDepleted":
        return FetchError(
            "X API credits 已耗尽，请前往 X Developer Console 购买或充值 credits。"
            f" 官方返回: {detail or 'CreditsDepleted'}"
        )
    if exc.code == 401:
        return FetchError("X Bearer Token 无效或已过期，请重新运行 `daily x login`")
    if exc.code == 403:
        return FetchError(
            "当前 X 应用权限不足，无法访问该接口。"
            f"{(' 官方返回: ' + detail) if detail else ''}"
        )
    if detail:
        return FetchError(f"{endpoint} returned HTTP {exc.code}: {detail}")
    return FetchError(f"{endpoint} returned HTTP {exc.code}")


def _fetch_x_json(endpoint: str, *, params: dict[str, str] | None = None, timeout: float) -> dict:
    url = endpoint
    if params:
        url = f"{endpoint}?{urlencode(params)}"

    request = Request(url, headers=_x_headers())
    try:
        with urlopen(request, timeout=timeout) as response:
            charset = response.headers.get_content_charset() or "utf-8"
            payload = response.read().decode(charset, errors="replace")
    except HTTPError as exc:
        raise _decode_x_error(exc, endpoint) from exc
    except URLError as exc:
        raise FetchError(f"{endpoint} is unavailable: {exc.reason}") from exc
    except TimeoutError as exc:
        raise FetchError(f"{endpoint} timed out after {timeout}s") from exc

    try:
        return json.loads(payload)
    except json.JSONDecodeError as exc:
        raise FetchError(f"{endpoint} returned invalid JSON") from exc


def _user_lookup(username: str, timeout: float) -> dict:
    normalized = username.strip().lstrip("@")
    if not normalized:
        raise ValueError("X 用户名不能为空")

    payload = _fetch_x_json(
        f"{X_API_BASE}/users/by/username/{normalized}",
        params={"user.fields": "description,public_metrics,verified"},
        timeout=timeout,
    )
    data = payload.get("data")
    if not isinstance(data, dict):
        errors = payload.get("errors") or []
        if errors:
            message = errors[0].get("detail") or errors[0].get("message") or "unknown error"
            raise FetchError(f"X 用户查询失败: {message}")
        raise FetchError("X 用户查询返回了空结果")
    return data


def fetch_x_usage(timeout: float = 10.0) -> dict:
    payload = _fetch_x_json(
        f"{X_API_BASE}/usage/tweets",
        timeout=timeout,
    )
    data = payload.get("data")
    if not isinstance(data, dict):
        raise FetchError("X usage 接口返回了空结果")
    return data


def _tweet_title_and_summary(text: str) -> tuple[str, str]:
    cleaned = " ".join((text or "").split()).strip()
    if not cleaned:
        return "", ""
    if len(cleaned) <= 110:
        return cleaned, ""
    return cleaned[:107].rstrip() + "...", cleaned


def fetch_x_user_tweets(
    username: str,
    *,
    limit: int,
    timeout: float,
    category: str,
) -> list[NewsItem]:
    user = _user_lookup(username, timeout=timeout)
    user_id = str(user.get("id") or "").strip()
    normalized = str(user.get("username") or username).strip().lstrip("@")
    display_name = str(user.get("name") or normalized).strip()
    if not user_id:
        raise FetchError("X 用户查询缺少用户 ID")

    payload = _fetch_x_json(
        f"{X_API_BASE}/users/{user_id}/tweets",
        params={
            "max_results": str(min(max(limit, 5), 100)),
            "exclude": "retweets,replies",
            "tweet.fields": "created_at,lang,public_metrics",
        },
        timeout=timeout,
    )

    data = payload.get("data")
    if data is None:
        errors = payload.get("errors") or []
        if errors:
            message = errors[0].get("detail") or errors[0].get("message") or "unknown error"
            raise FetchError(f"X 推文获取失败: {message}")
        return []
    if not isinstance(data, list):
        raise FetchError("X 推文接口返回了无效数据")

    items: list[NewsItem] = []
    for rank, entry in enumerate(data, start=1):
        tweet_id = str(entry.get("id") or "").strip()
        text = str(entry.get("text") or "").strip()
        title, summary = _tweet_title_and_summary(text)
        if not tweet_id or not title:
            continue

        metrics = entry.get("public_metrics") or {}
        tags: list[str] = []
        if metrics.get("like_count") is not None:
            tags.append(f"赞 {metrics['like_count']}")
        if metrics.get("retweet_count") is not None:
            tags.append(f"转推 {metrics['retweet_count']}")
        if metrics.get("reply_count") is not None:
            tags.append(f"回复 {metrics['reply_count']}")
        if metrics.get("quote_count") is not None:
            tags.append(f"引用 {metrics['quote_count']}")

        items.append(
            NewsItem(
                title=title,
                category=category,
                provider="x",
                feed="X",
                publisher=f"{display_name} (@{normalized})",
                summary=summary,
                link=f"https://x.com/{normalized}/status/{tweet_id}",
                published_at=format_pub_date(str(entry.get("created_at") or "")),
                rank=rank,
                language=str(entry.get("lang") or ""),
                tags=tags,
            )
        )
        if len(items) >= limit:
            break

    return items
