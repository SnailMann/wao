from __future__ import annotations

import argparse
from textwrap import dedent

from ..service.collector import collect_summary
from ..service.topics import DEFAULT_SUMMARY_TOPICS
from .args import add_common_fetch_args, emit_output, semantic_collection_options


def register(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    parser = subparsers.add_parser(
        "summary",
        help="输出默认 dashboard。",
        description=dedent(
            f"""\
            输出默认 dashboard:
              {", ".join(DEFAULT_SUMMARY_TOPICS)}

            默认仅 us-hot / china-hot 会触发 soft 过滤。
            us-hot 过滤后不足时，会用 Google News Top Stories 回补。
            """
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    add_common_fetch_args(parser)
    parser.set_defaults(handler=handle)


def handle(args) -> int:
    sections = collect_summary(
        source=args.source,
        limit=args.limit,
        timeout=args.timeout,
        **semantic_collection_options(args),
    )
    print(emit_output(args.format, sections), end="")
    return 0
