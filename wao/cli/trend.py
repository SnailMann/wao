from __future__ import annotations

import argparse
from textwrap import dedent

from ..service.trend import TREND_SOURCE_CHOICES, collect_trends
from .args import add_common_fetch_args, emit_output, semantic_collection_options


def register(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    parser = subparsers.add_parser(
        "trend",
        help="统一查看热榜源。",
        description=dedent(
            """\
            原子热榜能力，统一查看 Google Trends、百度热榜和 GitHub Trending。

            示例:
              wao trend
              wao trend --source google
              wao trend --source baidu --limit 20
              wao trend --source all --format json
            """
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--source",
        choices=TREND_SOURCE_CHOICES,
        default="auto",
        help="trend 可用来源：google、baidu、github 或 all；默认 auto=all。",
    )
    add_common_fetch_args(
        parser,
        include_source=False,
        exclude_label_help="追加需要过滤掉的语义标签；trend 默认不自动过滤，传入后才会分类拦截。",
    )
    parser.set_defaults(handler=handle)


def handle(args) -> int:
    sections = collect_trends(
        source=args.source,
        limit=args.limit,
        timeout=args.timeout,
        **semantic_collection_options(args),
    )
    print(emit_output(args.format, sections), end="")
    return 0
