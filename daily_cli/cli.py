from __future__ import annotations

import argparse
import json
from textwrap import dedent

from . import __version__
from .core.pipeline import collect_search, collect_summary, collect_topics
from .core.topics import DEFAULT_SUMMARY_TOPICS, list_topic_keys, list_topics
from .plugins.filters import list_filter_modes
from .renderers.output import render_json, render_text
from .runtime.semantic import MODEL_REPO_ID, SemanticError, download_model, list_content_labels


def positive_int(value: str) -> int:
    parsed = int(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("必须是大于 0 的整数")
    return parsed


def positive_float(value: str) -> float:
    parsed = float(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("必须是大于 0 的数字")
    return parsed


def _topic_summary() -> str:
    return ", ".join(list_topic_keys())


def _default_summary() -> str:
    return ", ".join(DEFAULT_SUMMARY_TOPICS)


def _top_level_help() -> str:
    return dedent(
        f"""\
        daily
          一个面向 Linux / macOS 的资讯命令行工具，聚合 Google、Baidu 和 GitHub 的公开信息源。

        Commands:
          topics
            列出全部 topic、默认来源、默认数量和默认过滤策略。
          summary
            输出默认 dashboard: {_default_summary()}
          fetch <topic ...>
            拉取一个或多个指定 topic。
          search <query>
            用 Google News 检索最新相关资讯。
          model download
            下载 model 模式所需模型；只用 tfidf 时可跳过。

        Topics:
          {_topic_summary()}

        Common options:
          --source auto|google|baidu|github|all
            指定来源；默认按 topic 自己的默认配置选择。
          --limit N
            控制每个 section 返回条数。
          --timeout SECONDS
            控制单个上游请求超时时间。
          --format text|json
            选择终端文本或 JSON 输出。

        Filter options:
          --filter-mode tfidf|model
            过滤模式；默认 tfidf，model 需先运行 `daily model download`。
          --exclude-label macro|industry|tech|public|soft
            额外过滤这些标签。
          --no-filter
            关闭过滤链路；不会为了过滤做额外抓取或分类。
          --no-semantic
            完全关闭标签分类、标签展示和过滤。

        Body options:
          --fetch-body
            对最终保留的链接再抓取正文。
          --body-timeout SECONDS
            控制正文抓取超时。
          --body-max-chars N
            控制每条正文最大字符数。

        Defaults:
          默认仅 us-hot / china-hot 过滤 soft。
          ai / finance / us-market / github / search 默认只抓取，不自动分类。
          us-hot 过滤后不足时，会按需用 Google News Top Stories 回补。

        Examples:
          daily summary
          daily summary --filter-mode tfidf --limit 5
          daily fetch us-hot china-hot --exclude-label soft
          daily fetch github --limit 10 --format json
          daily fetch us-hot --fetch-body --body-max-chars 3000
          daily search "人工智能" --google-locale cn
          daily model download

        More:
          运行 `daily <command> --help` 查看某个命令的详细参数。
        """
    )


def add_common_fetch_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--source",
        choices=("auto", "google", "baidu", "github", "all"),
        default="auto",
        help="选择数据来源，默认按 topic 自动挑选。",
    )
    parser.add_argument(
        "--limit",
        type=positive_int,
        default=None,
        help="每个 section 最多返回多少条；默认使用 topic 自己的默认值。",
    )
    parser.add_argument(
        "--timeout",
        type=positive_float,
        default=10.0,
        help="单个上游接口超时时间（秒）。",
    )
    parser.add_argument(
        "--format",
        choices=("text", "json"),
        default="text",
        help="输出格式。",
    )
    parser.add_argument(
        "--filter-mode",
        choices=list_filter_modes(),
        default="tfidf",
        help="标签/过滤模式；tfidf 为默认轻量模式，model 需要先下载模型。",
    )
    parser.add_argument(
        "--exclude-label",
        action="append",
        choices=list_content_labels(),
        default=None,
        help="追加需要过滤掉的语义标签；不传时仅 us-hot/china-hot 默认过滤 soft。",
    )
    parser.add_argument(
        "--no-filter",
        action="store_true",
        help="关闭标签过滤链路；不会为了过滤额外抓取或分类。",
    )
    parser.add_argument(
        "--no-semantic",
        action="store_true",
        help="关闭标签打标、标签展示和过滤。",
    )
    parser.add_argument(
        "--semantic-model-dir",
        default=None,
        help="本地语义模型目录；默认使用缓存目录。",
    )
    parser.add_argument(
        "--fetch-body",
        action="store_true",
        help="对最终保留结果的链接再用 Playwright 无头模式抓取正文。",
    )
    parser.add_argument(
        "--body-timeout",
        type=positive_float,
        default=15.0,
        help="正文抓取超时时间（秒）。",
    )
    parser.add_argument(
        "--body-max-chars",
        type=positive_int,
        default=4000,
        help="每条正文最多返回多少字符。",
    )


def add_search_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--limit",
        type=positive_int,
        default=5,
        help="最多返回多少条结果。",
    )
    parser.add_argument(
        "--timeout",
        type=positive_float,
        default=10.0,
        help="Google News 接口超时时间（秒）。",
    )
    parser.add_argument(
        "--format",
        choices=("text", "json"),
        default="text",
        help="输出格式。",
    )
    parser.add_argument(
        "--filter-mode",
        choices=list_filter_modes(),
        default="tfidf",
        help="标签/过滤模式；tfidf 为默认轻量模式，model 需要先下载模型。",
    )
    parser.add_argument(
        "--exclude-label",
        action="append",
        choices=list_content_labels(),
        default=None,
        help="追加需要过滤掉的语义标签；search 默认不启用过滤，传入后才会分类拦截。",
    )
    parser.add_argument(
        "--no-filter",
        action="store_true",
        help="关闭标签过滤链路；不会为了过滤额外抓取或分类。",
    )
    parser.add_argument(
        "--no-semantic",
        action="store_true",
        help="关闭标签打标、标签展示和过滤。",
    )
    parser.add_argument(
        "--semantic-model-dir",
        default=None,
        help="本地语义模型目录；默认使用缓存目录。",
    )
    parser.add_argument(
        "--fetch-body",
        action="store_true",
        help="对最终保留结果的链接再用 Playwright 无头模式抓取正文。",
    )
    parser.add_argument(
        "--body-timeout",
        type=positive_float,
        default=15.0,
        help="正文抓取超时时间（秒）。",
    )
    parser.add_argument(
        "--body-max-chars",
        type=positive_int,
        default=4000,
        help="每条正文最多返回多少字符。",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="daily",
        description="快速检索每日热门话题、专题资讯与 GitHub Trending。",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=_top_level_help(),
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")

    subparsers = parser.add_subparsers(dest="command", required=True, title="commands")

    topics_parser = subparsers.add_parser(
        "topics",
        help="列出支持的 topics。",
        description="列出全部 topics、默认来源、默认 limit 和默认过滤标签。",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    topics_parser.add_argument(
        "--format",
        choices=("text", "json"),
        default="text",
        help="输出格式。",
    )

    model_parser = subparsers.add_parser(
        "model",
        help="下载或查看 model 过滤模式所需模型。",
        description="管理 model 过滤模式所需的语义模型文件。",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    model_subparsers = model_parser.add_subparsers(dest="model_command", required=True)
    model_download_parser = model_subparsers.add_parser(
        "download",
        help="提前下载 model 模式的语义模型文件。",
        description=(
            f"下载 model 模式使用的语义模型。\n当前模型: {MODEL_REPO_ID}\n"
            "如果你只使用 --filter-mode tfidf，可以不下载。"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    model_download_parser.add_argument(
        "--model-dir",
        default=None,
        help="模型下载目录；默认使用缓存目录。",
    )
    model_download_parser.add_argument(
        "--force",
        action="store_true",
        help="强制重新下载模型文件。",
    )

    summary_parser = subparsers.add_parser(
        "summary",
        help="输出默认 dashboard。",
        description=dedent(
            f"""\
            输出默认 dashboard:
              {_default_summary()}

            默认仅 us-hot / china-hot 会触发 soft 过滤。
            us-hot 过滤后不足时，会用 Google News Top Stories 回补。
            """
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    add_common_fetch_args(summary_parser)

    fetch_parser = subparsers.add_parser(
        "fetch",
        help="获取一个或多个 topics。",
        description=dedent(
            f"""\
            获取一个或多个 topics。

            可选 topics:
              {_topic_summary()}

            默认仅 us-hot / china-hot 会触发 soft 过滤。
            """
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    fetch_parser.add_argument(
        "topics",
        nargs="+",
        choices=list_topic_keys(),
        help="要查询的 topics。",
    )
    add_common_fetch_args(fetch_parser)

    search_parser = subparsers.add_parser(
        "search",
        help="按关键词查询最新相关信息。",
        description=dedent(
            """\
            按关键词通过 Google News 查询最新相关信息。

            search 默认只做检索，不自动分类过滤；
            当你显式传入 --exclude-label 时，才会启动标签过滤。
            """
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    search_parser.add_argument("query", help="要查询的关键词。")
    add_search_args(search_parser)
    search_parser.add_argument(
        "--google-locale",
        choices=("auto", "us", "cn"),
        default="auto",
        help="Google News 查询地区；auto 会根据关键词自动判断。",
    )

    return parser


def emit_output(format_name: str, sections) -> str:
    if format_name == "json":
        return render_json(sections)
    return render_text(sections)


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        if args.command == "topics":
            if args.format == "json":
                payload = {
                    "topics": [
                        {
                            "key": spec.key,
                            "label": spec.label,
                            "description": spec.description,
                            "supported_sources": list(spec.supported_sources),
                            "default_sources": list(spec.default_sources),
                            "default_limit": spec.default_limit,
                            "default_excluded_labels": list(spec.default_excluded_labels),
                        }
                        for spec in list_topics()
                    ]
                }
                print(json.dumps(payload, ensure_ascii=False, indent=2))
                return 0

            for spec in list_topics():
                supported = ", ".join(spec.supported_sources)
                default = ", ".join(spec.default_sources)
                excluded = ", ".join(spec.default_excluded_labels) or "无"
                print(f"{spec.key}: {spec.label}")
                print(f"  {spec.description}")
                print(f"  supported={supported} default={default} limit={spec.default_limit}")
                print(f"  exclude={excluded}")
            return 0

        if args.command == "model" and args.model_command == "download":
            model_path = download_model(model_dir=args.model_dir, force=args.force)
            print(f"模型: {MODEL_REPO_ID}")
            print(f"目录: {model_path}")
            print("状态: 已下载，可直接用于 summary/fetch/search")
            return 0

        if args.command == "summary":
            sections = collect_summary(
                source=args.source,
                limit=args.limit,
                timeout=args.timeout,
                semantic_enabled=not args.no_semantic,
                semantic_filter=not args.no_semantic and not args.no_filter,
                excluded_labels=tuple(args.exclude_label) if args.exclude_label else None,
                semantic_model_dir=args.semantic_model_dir,
                filter_mode=args.filter_mode,
                fetch_body=args.fetch_body,
                body_timeout=args.body_timeout,
                body_max_chars=args.body_max_chars,
            )
            print(emit_output(args.format, sections), end="")
            return 0

        if args.command == "fetch":
            sections = collect_topics(
                args.topics,
                source=args.source,
                limit=args.limit,
                timeout=args.timeout,
                semantic_enabled=not args.no_semantic,
                semantic_filter=not args.no_semantic and not args.no_filter,
                excluded_labels=tuple(args.exclude_label) if args.exclude_label else None,
                semantic_model_dir=args.semantic_model_dir,
                filter_mode=args.filter_mode,
                fetch_body=args.fetch_body,
                body_timeout=args.body_timeout,
                body_max_chars=args.body_max_chars,
            )
            print(emit_output(args.format, sections), end="")
            return 0

        if args.command == "search":
            section = collect_search(
                query=args.query,
                limit=args.limit,
                timeout=args.timeout,
                google_locale=args.google_locale,
                semantic_enabled=not args.no_semantic,
                semantic_filter=not args.no_semantic and not args.no_filter,
                excluded_labels=tuple(args.exclude_label) if args.exclude_label else None,
                semantic_model_dir=args.semantic_model_dir,
                filter_mode=args.filter_mode,
                fetch_body=args.fetch_body,
                body_timeout=args.body_timeout,
                body_max_chars=args.body_max_chars,
            )
            print(emit_output(args.format, [section]), end="")
            return 0
    except (ValueError, SemanticError) as exc:
        parser.error(str(exc))

    return 1
