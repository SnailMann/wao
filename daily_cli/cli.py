from __future__ import annotations

import argparse
import json

from . import __version__
from .output import render_json, render_text
from .semantic import MODEL_REPO_ID, SemanticError, download_model, list_content_labels
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
        help="关闭语义打标与标签展示。",
    )
    parser.add_argument(
        "--no-filter",
        action="store_true",
        help="保留语义标签，但不按标签过滤结果。",
    )
    parser.add_argument(
        "--exclude-label",
        action="append",
        choices=list_content_labels(),
        default=None,
        help="追加需要过滤掉的语义标签；默认过滤 soft。",
    )
    parser.add_argument(
        "--semantic-model-dir",
        default=None,
        help="本地语义模型目录；默认使用 ~/.cache/daily-cli/models 下的预下载目录。",
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
        help="关闭语义打标与标签展示。",
    )
    parser.add_argument(
        "--no-filter",
        action="store_true",
        help="保留语义标签，但不按标签过滤结果。",
    )
    parser.add_argument(
        "--exclude-label",
        action="append",
        choices=list_content_labels(),
        default=None,
        help="追加需要过滤掉的语义标签；默认过滤 soft。",
    )
    parser.add_argument(
        "--semantic-model-dir",
        default=None,
        help="本地语义模型目录；默认使用 ~/.cache/daily-cli/models 下的预下载目录。",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="daily-cli",
        description="快速检索每日美国/中国热点、AI 趋势、金融热点的命令行工具。",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")

    subparsers = parser.add_subparsers(dest="command", required=True)

    presets_parser = subparsers.add_parser("presets", help="查看支持的预设。")
    presets_parser.add_argument(
        "--format",
        choices=("text", "json"),
        default="text",
        help="输出格式。",
    )

    model_parser = subparsers.add_parser("model", help="下载或查看语义过滤所需模型。")
    model_subparsers = model_parser.add_subparsers(dest="model_command", required=True)
    model_download_parser = model_subparsers.add_parser("download", help="提前下载语义过滤模型文件。")
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

    summary_parser = subparsers.add_parser("summary", help="输出默认五类每日摘要。")
    add_common_fetch_args(summary_parser)

    fetch_parser = subparsers.add_parser("fetch", help="获取一个或多个预设分组。")
    fetch_parser.add_argument(
        "presets",
        nargs="+",
        choices=tuple(spec.key for spec in list_presets()),
        help="要查询的预设。",
    )
    add_common_fetch_args(fetch_parser)

    search_parser = subparsers.add_parser("search", help="按关键词查询最新相关信息。")
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
            )
            print(emit_output(args.format, [section]), end="")
            return 0
    except (ValueError, SemanticError) as exc:
        parser.error(str(exc))

    return 1
