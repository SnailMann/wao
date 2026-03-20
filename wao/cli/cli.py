from __future__ import annotations

import argparse

from .. import __version__
from ..plugins.semantic import SemanticError
from ..service.topics import DEFAULT_SUMMARY_TOPICS, list_topic_keys
from . import fetch, model, rss, search, summary, topics, trend, x


class WaoTopLevelParser(argparse.ArgumentParser):
    """Top-level parser with a curated help panel."""

    def format_help(self) -> str:
        return _top_level_help()


def _topic_summary() -> str:
    return ", ".join(list_topic_keys())


def _default_summary() -> str:
    return ", ".join(DEFAULT_SUMMARY_TOPICS)


def _format_help_rows(rows: list[tuple[str, str]], *, indent: int = 2, width: int = 20) -> str:
    prefix = " " * indent
    return "\n".join(f"{prefix}{left:<{width}} {right}" for left, right in rows)


def _top_level_help() -> str:
    options = _format_help_rows(
        [
            ("-h, --help", "Display help for command"),
            ("--version", "output the version number"),
        ],
        width=20,
    )
    commands = _format_help_rows(
        [
            ("topics", "List supported business topics."),
            ("trend", "View trend sources through one unified command."),
            ("x", "Manage X Bearer Token credentials and subcommands."),
            ("rss", "Fetch RSSHub or RSS/Atom feeds and manage saved subscriptions."),
            ("model", "Download or inspect the model filter assets."),
            ("summary", f"Output the default dashboard: {_default_summary()}."),
            ("fetch", "Fetch one or more business topics."),
            ("search", "Search Google News, X posts, X user posts, or X news."),
        ],
        width=20,
    )
    common_flags = _format_help_rows(
        [
            ("--source auto|google|baidu|github|all", "Choose workflow source selection; trend/search have their own source switches."),
            ("--limit N", "Control the maximum number of items in each section."),
            ("--timeout SECONDS", "Control the timeout for a single upstream request."),
            ("--format text|json", "Choose text or JSON output."),
            ("--filter-mode tfidf|model", "Choose the lightweight filter or the embedding-model filter."),
            ("--exclude-label macro|industry|tech|public|soft", "Exclude one or more semantic labels."),
            ("--no-filter", "Disable filtering without disabling plain fetching."),
            ("--no-semantic", "Disable labeling, filtering, and semantic metadata."),
            ("--fetch-body", "Fetch body text for the final kept items."),
        ],
        width=46,
    )
    examples = _format_help_rows(
        [
            ("wao trend --help", "Show detailed help for the trend command."),
            ("wao trend --source baidu --limit 20", "View 20 items from Baidu Hotboard."),
            ('wao search "OpenAI" --source x', "Search recent X posts for a keyword."),
            ("wao search elonmusk --source x-user", "Fetch recent public posts from an X user."),
            ("wao rss fetch https://36kr.com/feed", "Preview a plain RSS feed without saving it."),
            ("wao rss add rsshub://twitter/user/elonmusk --name Elon", "Save an RSSHub subscription."),
            ("wao summary", "Render the default dashboard."),
            ("wao fetch us-hot china-hot --exclude-label soft", "Fetch two topics with an explicit filter."),
            ("wao fetch us-hot --fetch-body --body-max-chars 3000", "Fetch a topic and enrich kept items with body text."),
            ("wao x login", "Save an X Bearer Token for X-based search sources."),
            ("wao model download", "Download the optional embedding model for model filter mode."),
        ],
        width=58,
    )
    lines = [
        "Usage: wao [options] [command]",
        "",
        "Options:",
        options,
        "",
        "Commands:",
        commands,
        "",
        "Common flags:",
        common_flags,
        "",
        "Defaults:",
        f"  Topics: {_topic_summary()}",
        f"  Summary default topics: {_default_summary()}",
        "  Default filter scope: only us-hot / china-hot filter soft by default",
        "  Default no-filter scope: ai / finance / us-market / github / search",
        "  Refill rule: us-hot refills with Google News Top Stories after filtering",
        "  默认仅 us-hot / china-hot 过滤 soft",
        "  us-hot 过滤后不足时，会按需用 Google News Top Stories 回补",
        "  Source switches: trend=google|baidu|github|all, search=google|x|x-user|x-news|all",
        "",
        "Examples:",
        examples,
        "",
    ]
    return "\n".join(lines)


def build_parser() -> argparse.ArgumentParser:
    parser = WaoTopLevelParser(
        prog="wao",
        description="哇哦：快速检索热门趋势、专题资讯、RSS 与跨源搜索结果。",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")

    subparsers = parser.add_subparsers(dest="command", required=True, title="commands")
    for register in (
        topics.register,
        trend.register,
        x.register,
        rss.register,
        model.register,
        summary.register,
        fetch.register,
        search.register,
    ):
        register(subparsers)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        handler = getattr(args, "handler", None)
        if handler is None:
            parser.error("缺少命令处理器")
        return handler(args)
    except (ValueError, SemanticError) as exc:
        parser.error(str(exc))
    return 1
