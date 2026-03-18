from __future__ import annotations

import argparse
import json
from textwrap import dedent

from . import __version__
from .output import render_json, render_text
from .semantic import MODEL_REPO_ID, SemanticError, download_model, list_content_labels, list_filter_backends
from .service import collect_presets, collect_search, collect_summary, list_presets


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


def _preset_summary() -> str:
    return "us-hot, china-hot, ai, finance, us-market, github"


def _top_level_help_epilog() -> str:
    return dedent(
        f"""\
        命令:
          presets
            查看全部预设、默认来源、默认 limit 和默认过滤标签。
          model download
            下载 model 过滤模式所需模型；仅使用 tfidf 时可跳过。
          summary
            输出默认五类摘要: us-hot, china-hot, ai, finance, github
          fetch <preset...>
            拉取一个或多个预设，可选: {_preset_summary()}
          search <query>
            按关键词通过 Google News 查询最新信息

        常用查询参数:
          --source auto|google|baidu|github|all
            指定数据来源；默认按预设自动选择。
          --limit N
            控制每个分组返回条数。
          --timeout SECONDS
            控制单个上游接口超时时间。
          --format text|json
            切换终端文本或 JSON 输出。

        过滤与标签参数:
          --filter-mode tfidf|model
            选择过滤后端；默认 tfidf，model 需先执行 `daily-cli model download`。
          --exclude-label macro|industry|tech|public|soft
            追加要过滤掉的标签。
          --no-filter
            关闭过滤链路；不会为了过滤做额外抓取或分类。
          --no-semantic
            完全关闭标签分类、标签展示和过滤。
          --semantic-model-dir PATH
            指定本地语义模型目录。

        预设与默认行为:
          预设:
            {_preset_summary()}
          默认仅 us-hot / china-hot 过滤 soft。
          ai / finance / us-market / github / search 默认不启动分类。
          us-hot 过滤后不足时，会按需用 Google News Top Stories 回补。
          search 默认只检索；显式传入 --exclude-label 后才会启动过滤。

        提示:
          运行 `daily-cli <command> --help` 查看该命令的详细参数。

        常用示例:
          daily-cli summary
          daily-cli summary --filter-mode tfidf --limit 5
          daily-cli fetch us-hot china-hot --exclude-label soft
          daily-cli fetch github --limit 10 --format json
          daily-cli search "人工智能" --google-locale cn
          daily-cli model download
        """
    )


def add_common_fetch_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--source",
        choices=("auto", "google", "baidu", "github", "all"),
        default="auto",
        help="选择数据来源，默认按预设自动挑选。",
    )
    parser.add_argument(
        "--limit",
        type=positive_int,
        default=None,
        help="每个分组最多返回多少条结果；默认使用各预设自己的默认值。",
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
        "--no-semantic",
        action="store_true",
        help="关闭语义打标、标签展示和过滤。",
    )
    parser.add_argument(
        "--no-filter",
        action="store_true",
        help="关闭标签过滤链路；不会为了过滤额外抓取或分类。",
    )
    parser.add_argument(
        "--exclude-label",
        action="append",
        choices=list_content_labels(),
        default=None,
        help="追加需要过滤掉的语义标签；不传时仅 us-hot/china-hot 默认过滤 soft。",
    )
    parser.add_argument(
        "--semantic-model-dir",
        default=None,
        help="本地语义模型目录；默认使用 ~/.cache/daily-cli/models 下的预下载目录。",
    )
    parser.add_argument(
        "--filter-mode",
        choices=list_filter_backends(),
        default="tfidf",
        help="标签/过滤模式；tfidf 为默认轻量模式，model 需要先下载模型。",
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
        "--no-semantic",
        action="store_true",
        help="关闭语义打标、标签展示和过滤。",
    )
    parser.add_argument(
        "--no-filter",
        action="store_true",
        help="关闭标签过滤链路；不会为了过滤额外抓取或分类。",
    )
    parser.add_argument(
        "--exclude-label",
        action="append",
        choices=list_content_labels(),
        default=None,
        help="追加需要过滤掉的语义标签；search 默认不启用过滤，传入后才会分类拦截。",
    )
    parser.add_argument(
        "--semantic-model-dir",
        default=None,
        help="本地语义模型目录；默认使用 ~/.cache/daily-cli/models 下的预下载目录。",
    )
    parser.add_argument(
        "--filter-mode",
        choices=list_filter_backends(),
        default="tfidf",
        help="标签/过滤模式；tfidf 为默认轻量模式，model 需要先下载模型。",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="daily-cli",
        description=(
            "快速检索每日美国/中国热点、AI 趋势、金融热点和 GitHub Trending 的命令行工具。"
        ),
        formatter_class=argparse.RawTextHelpFormatter,
        epilog=_top_level_help_epilog(),
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")

    subparsers = parser.add_subparsers(dest="command", required=True, title="commands")

    presets_parser = subparsers.add_parser(
        "presets",
        help="查看支持的预设。",
        description="列出所有预设、默认来源、默认 limit 和默认过滤标签。",
        formatter_class=argparse.RawTextHelpFormatter,
    )
    presets_parser.add_argument(
        "--format",
        choices=("text", "json"),
        default="text",
        help="输出格式。",
    )

    model_parser = subparsers.add_parser(
        "model",
        help="下载或查看语义过滤所需模型。",
        description="管理 model 过滤模式所需的语义模型文件。",
        formatter_class=argparse.RawTextHelpFormatter,
    )
    model_subparsers = model_parser.add_subparsers(dest="model_command", required=True)
    model_download_parser = model_subparsers.add_parser(
        "download",
        help="提前下载语义过滤模型文件。",
        description=(
            f"下载 model 模式使用的语义模型。\n当前模型: {MODEL_REPO_ID}\n"
            "如果你只使用 --filter-mode tfidf，可以不下载。"
        ),
        formatter_class=argparse.RawTextHelpFormatter,
    )
    model_download_parser.add_argument(
        "--model-dir",
        default=None,
        help="模型下载目录；默认使用 ~/.cache/daily-cli/models 下的缓存目录。",
    )
    model_download_parser.add_argument(
        "--force",
        action="store_true",
        help="强制重新下载模型文件。",
    )

    summary_parser = subparsers.add_parser(
        "summary",
        help="输出默认五类每日摘要。",
        description=dedent(
            """\
            输出默认五类摘要:
              us-hot, china-hot, ai, finance, github

            默认仅 us-hot / china-hot 会触发 soft 过滤。
            us-hot 过滤后不足时，会用 Google News Top Stories 回补。
            """
        ),
        formatter_class=argparse.RawTextHelpFormatter,
    )
    add_common_fetch_args(summary_parser)

    fetch_parser = subparsers.add_parser(
        "fetch",
        help="获取一个或多个预设分组。",
        description=dedent(
            f"""\
            获取一个或多个预设分组。

            可选预设:
              {_preset_summary()}

            默认仅 us-hot / china-hot 会触发 soft 过滤。
            """
        ),
        formatter_class=argparse.RawTextHelpFormatter,
    )
    fetch_parser.add_argument(
        "presets",
        nargs="+",
        choices=tuple(spec.key for spec in list_presets()),
        help="要查询的预设。",
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
        formatter_class=argparse.RawTextHelpFormatter,
    )
    search_parser.add_argument("query", help="要查询的关键词。")
    add_search_args(search_parser)
    search_parser.add_argument(
        "--google-locale",
        choices=("auto", "us", "cn"),
        default="auto",
        help="Google News 查询地区，auto 会根据关键词自动判断。",
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
        if args.command == "presets":
            if args.format == "json":
                payload = {
                    "presets": [
                        {
                            "key": spec.key,
                            "label": spec.label,
                            "description": spec.description,
                            "supported_sources": list(spec.supported_sources),
                            "default_sources": list(spec.default_sources),
                            "default_limit": spec.default_limit,
                            "default_excluded_labels": list(spec.default_excluded_labels),
                        }
                        for spec in list_presets()
                    ]
                }
                print(json.dumps(payload, ensure_ascii=False, indent=2))
                return 0

            for spec in list_presets():
                supported = ", ".join(spec.supported_sources)
                default = ", ".join(spec.default_sources)
                excluded = ", ".join(spec.default_excluded_labels) or "无"
                print(f"{spec.key}: {spec.label}")
                print(f"  {spec.description}")
                print(f"  supported={supported} default={default} limit={spec.default_limit}")
                print(f"  exclude={excluded}")
            return 0

        if args.command == "model":
            if args.model_command == "download":
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
            )
            print(emit_output(args.format, sections), end="")
            return 0

        if args.command == "fetch":
            sections = collect_presets(
                args.presets,
                source=args.source,
                limit=args.limit,
                timeout=args.timeout,
                semantic_enabled=not args.no_semantic,
                semantic_filter=not args.no_semantic and not args.no_filter,
                excluded_labels=tuple(args.exclude_label) if args.exclude_label else None,
                semantic_model_dir=args.semantic_model_dir,
                filter_mode=args.filter_mode,
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
            )
            print(emit_output(args.format, [section]), end="")
            return 0
    except (ValueError, SemanticError) as exc:
        parser.error(str(exc))

    return 1
