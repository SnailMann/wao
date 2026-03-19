from __future__ import annotations

import re
from urllib.parse import urljoin, urlparse

from .models import NewsItem

BODY_RESOURCE_SKIP_TYPES = {"font", "image", "media"}
DEFAULT_BODY_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/123.0.0.0 Safari/537.36"
)
ARTICLE_SELECTORS = (
    "article",
    "main article",
    "[role='main'] article",
    "main",
    "[role='main']",
    ".article-content",
    ".article-body",
    ".post-content",
    ".entry-content",
    ".story-body",
    ".story-content",
)
REMOVE_SELECTORS = (
    "script, style, noscript, iframe, svg, canvas, form, button, input, textarea, "
    "nav, footer, header, aside, [aria-hidden='true'], .advertisement, .ads, .share-tools"
)
EXTRACTION_SCRIPT = f"""
() => {{
  const selectors = {list(ARTICLE_SELECTORS)!r};
  const removeSelectors = {REMOVE_SELECTORS!r};

  const cleanText = (node) => {{
    if (!node) return "";
    const clone = node.cloneNode(true);
    clone.querySelectorAll(removeSelectors).forEach((element) => element.remove());
    const text = (clone.innerText || clone.textContent || "")
      .replace(/\\s+/g, " ")
      .trim();
    return text;
  }};

  const candidates = [];
  for (const selector of selectors) {{
    for (const node of document.querySelectorAll(selector)) {{
      const text = cleanText(node);
      if (text.length >= 200) {{
        candidates.push({{ selector, text, length: text.length }});
      }}
    }}
  }}

  let best = candidates.sort((left, right) => right.length - left.length)[0];
  if (!best) {{
    const bodyText = cleanText(document.body);
    best = {{ selector: "body", text: bodyText, length: bodyText.length }};
  }}

  return {{
    title: document.title || "",
    url: window.location.href,
    selector: best.selector,
    text: best.text,
  }};
}}
"""
BAIDU_RESULT_SCRIPT = """
() => {
  const selectors = [
    "#content_left h3 a[href]",
    "#content_left a[href]",
    "article a[href]",
    "a[href]"
  ];
  const urls = [];
  for (const selector of selectors) {
    for (const element of document.querySelectorAll(selector)) {
      const href = element.getAttribute("href");
      if (!href || href.startsWith("javascript:")) continue;
      const absolute = new URL(href, window.location.href).href;
      urls.push(absolute);
    }
  }
  return Array.from(new Set(urls));
}
"""


class BodyFetchError(RuntimeError):
    """Raised when Playwright正文抓取不可用。"""


def _load_playwright():
    try:
        from playwright.sync_api import Error as PlaywrightError
        from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise BodyFetchError(
            "正文抓取依赖未安装，请先执行 `python3 -m pip install .`。"
        ) from exc
    return sync_playwright, PlaywrightError, PlaywrightTimeoutError


def _normalize_body_text(text: str, max_chars: int) -> str:
    normalized = re.sub(r"\s+", " ", text or "").strip()
    if len(normalized) <= max_chars:
        return normalized
    return normalized[:max_chars].rstrip()


def _is_baidu_search_url(url: str) -> bool:
    parsed = urlparse(url)
    return parsed.netloc.endswith("baidu.com") and parsed.path == "/s"


def _is_google_news_url(url: str) -> bool:
    parsed = urlparse(url)
    return parsed.netloc.endswith("news.google.com")


def _pick_baidu_result_url(urls: list[str]) -> str:
    for candidate in urls:
        parsed = urlparse(candidate)
        if not parsed.scheme.startswith("http"):
            continue
        if parsed.netloc.endswith("baidu.com") and parsed.path == "/s":
            continue
        return candidate
    return ""


def _prepare_page(page) -> None:
    def route_handler(route):
        if route.request.resource_type in BODY_RESOURCE_SKIP_TYPES:
            route.abort()
            return
        route.continue_()

    page.route("**/*", route_handler)


def _goto(page, url: str, timeout_ms: int) -> None:
    page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
    page.wait_for_timeout(500)


def _wait_for_google_news_redirect(page) -> None:
    if not _is_google_news_url(page.url):
        return
    for _ in range(8):
        page.wait_for_timeout(500)
        if not _is_google_news_url(page.url):
            return


def _resolve_article_url(page, url: str, timeout_ms: int) -> str:
    _goto(page, url, timeout_ms)
    _wait_for_google_news_redirect(page)
    if not _is_baidu_search_url(page.url):
        page.wait_for_timeout(1200)
        return page.url

    candidates = page.evaluate(BAIDU_RESULT_SCRIPT)
    target = _pick_baidu_result_url(candidates or [])
    if not target:
        return page.url

    _goto(page, target, timeout_ms)
    page.wait_for_timeout(1200)
    return page.url


def _looks_like_verification_page(text: str, url: str, title: str = "") -> bool:
    lowered = f"{title} {text}".casefold()
    return any(
        marker in lowered
        for marker in (
            "captcha",
            "access to this page has been denied",
            "access denied",
            "just a moment",
            "verify you are human",
            "press and hold",
            "enable javascript and cookies",
            "captcha-delivery",
        )
    ) or "captcha" in url.casefold()


def _looks_like_browser_error_url(url: str) -> bool:
    lowered = url.casefold()
    return lowered.startswith("chrome-error://") or lowered.startswith("about:blank")


def _extract_payload_with_retry(page, playwright_error, timeout_ms: int) -> dict[str, str]:
    last_error: Exception | None = None
    for attempt in range(3):
        try:
            if attempt:
                page.wait_for_timeout(1000)
            try:
                page.wait_for_load_state("load", timeout=min(timeout_ms, 4000))
            except Exception:
                pass
            return page.evaluate(EXTRACTION_SCRIPT)
        except playwright_error as exc:
            last_error = exc
            message = str(exc)
            if "Execution context was destroyed" not in message and "Cannot find context with specified id" not in message:
                raise
    if last_error is not None:
        raise last_error
    return {"title": "", "url": page.url, "selector": "", "text": ""}


def _extract_body_inner_text(page) -> str:
    try:
        return page.locator("body").inner_text(timeout=5000)
    except Exception:
        return ""


def fetch_item_bodies(
    items: list[NewsItem],
    timeout: float,
    max_chars: int,
) -> list[NewsItem]:
    if not items:
        return items

    sync_playwright, PlaywrightError, PlaywrightTimeoutError = _load_playwright()
    timeout_ms = int(timeout * 1000)

    try:
        with sync_playwright() as playwright:
            try:
                browser = playwright.chromium.launch(headless=True)
            except PlaywrightError as exc:
                raise BodyFetchError(
                    "Playwright Chromium 不可用，请先执行 `python3 -m playwright install chromium`。"
                ) from exc

            context = browser.new_context(
                ignore_https_errors=True,
                user_agent=DEFAULT_BODY_USER_AGENT,
            )
            try:
                for item in items:
                    item.body_text = ""
                    item.body_url = ""
                    item.body_error = ""

                    if not item.link or not item.link.startswith("http"):
                        item.body_error = "缺少可抓取链接"
                        continue

                    page = context.new_page()
                    try:
                        _prepare_page(page)
                        resolved_url = _resolve_article_url(page, item.link, timeout_ms)
                        payload = _extract_payload_with_retry(page, PlaywrightError, timeout_ms)
                        body_text = _normalize_body_text(payload.get("text", ""), max_chars=max_chars)
                        item.body_url = payload.get("url") or resolved_url or item.link
                        page_title = payload.get("title", "")
                        if not body_text:
                            body_text = _normalize_body_text(_extract_body_inner_text(page), max_chars=max_chars)
                        if _looks_like_browser_error_url(item.body_url):
                            item.body_error = "浏览器未能打开目标页面"
                        elif _looks_like_verification_page(body_text, item.body_url, page_title):
                            item.body_error = "命中站点验证或验证码页"
                        elif not body_text:
                            item.body_error = "正文为空"
                        else:
                            item.body_text = body_text
                    except PlaywrightTimeoutError:
                        item.body_error = f"抓取超时（>{timeout:.1f}s）"
                    except PlaywrightError as exc:
                        item.body_error = str(exc).splitlines()[0][:160]
                    finally:
                        page.close()
            finally:
                context.close()
                browser.close()
    except BodyFetchError:
        raise
    except Exception as exc:  # pragma: no cover - defensive fallback
        raise BodyFetchError(f"正文抓取失败: {exc}") from exc

    return items
