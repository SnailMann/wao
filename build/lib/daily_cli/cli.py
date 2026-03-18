from __future__ import annotations

import argparse
import json

from . import __version__
from .output import render_json, render_text
from .service import collect_preset, collect_search, collect_summary, list_presets


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
        choices=("auto", "google", "baidu", "all"),
        default="auto",
        help="选择数据来源，默认按预设自动挑选。",
    )
    parser.add_argument(
        "--limit",
        type=positive_int,
        default=5,
        help="每个分组最多返回多少条结果。",
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

    summary_parser = subparsers.add_parser("summary", help="输出默认四类每日摘要。")
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
    add_common_fetch_args(search_parser)
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
                        }
                        for spec in list_presets()
                    ]
                }
                print(json.dumps(payload, ensure_ascii=False, indent=2))
                return 0

            for spec in list_presets():
                supported = ", ".join(spec.supported_sources)
                default = ", ".join(spec.default_sources)
                print(f"{spec.key}: {spec.label}")
                print(f"  {spec.description}")
                print(f"  supported={supported} default={default}")
            return 0

        if args.command == "summary":
            sections = collect_summary(source=args.source, limit=args.limit, timeout=args.timeout)
            print(emit_output(args.format, sections), end="")
            return 0

        if args.command == "fetch":
            sections = [
                collect_preset(key, source=args.source, limit=args.limit, timeout=args.timeout)
                for key in args.presets
            ]
            print(emit_output(args.format, sections), end="")
            return 0

        if args.command == "search":
            section = collect_search(
                query=args.query,
                source=args.source,
                limit=args.limit,
                timeout=args.timeout,
                google_locale=args.google_locale,
            )
            print(emit_output(args.format, [section]), end="")
            return 0
    except ValueError as exc:
        parser.error(str(exc))

    return 1
