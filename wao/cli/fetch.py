from __future__ import annotations

import argparse
from textwrap import dedent

from ..service.collector import collect_topics
from ..service.topics import list_topic_keys
from .args import add_common_fetch_args, emit_output, semantic_collection_options


def register(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    parser = subparsers.add_parser(
        "fetch",
        help="获取一个或多个 topics。",
        description=dedent(
            f"""\
            获取一个或多个 topics。

            可选 topics:
              {", ".join(list_topic_keys())}

            默认仅 us-hot / china-hot 会触发 soft 过滤。
            """
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "topics",
        nargs="+",
        choices=list_topic_keys(),
        help="要查询的 topics。",
    )
    add_common_fetch_args(parser)
    parser.set_defaults(handler=handle)


def handle(args) -> int:
    sections = collect_topics(
        args.topics,
        source=args.source,
        limit=args.limit,
        timeout=args.timeout,
        **semantic_collection_options(args),
    )
    print(emit_output(args.format, sections), end="")
    return 0
