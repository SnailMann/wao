from __future__ import annotations

import argparse
from textwrap import dedent

from ..service.search import collect_search
from .args import add_search_args, emit_output, semantic_collection_options


def register(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    parser = subparsers.add_parser(
        "search",
        help="按关键词查询最新相关信息。",
        description=dedent(
            """\
            按关键词通过 Google News、X recent search、X user posts 或 X news search 查询最新相关信息。

            search 默认 source=google，只做检索，不自动分类过滤；
            当你显式传入 --exclude-label 时，才会启动标签过滤。

            当 --source x-user 时，query 会被当作 X 用户名处理。
            """
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("query", help="要查询的关键词。")
    add_search_args(parser)
    parser.add_argument(
        "--google-locale",
        choices=("auto", "us", "cn"),
        default="auto",
        help="Google News 查询地区；auto 会根据关键词自动判断。",
    )
    parser.set_defaults(handler=handle)


def handle(args) -> int:
    section = collect_search(
        query=args.query,
        limit=args.limit,
        timeout=args.timeout,
        source=args.source,
        google_locale=args.google_locale,
        **semantic_collection_options(args),
    )
    print(emit_output(args.format, [section]), end="")
    return 0
