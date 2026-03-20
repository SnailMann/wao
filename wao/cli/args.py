from __future__ import annotations

import argparse

from ..core.output import render_json, render_text
from ..plugins.filters import list_filter_modes
from ..plugins.semantic import list_content_labels
from ..service.search import SEARCH_SOURCE_CHOICES


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


def add_common_fetch_args(
    parser: argparse.ArgumentParser,
    *,
    include_source: bool = True,
    exclude_label_help: str = "追加需要过滤掉的语义标签；不传时仅 us-hot/china-hot 默认过滤 soft。",
) -> None:
    if include_source:
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
        help=exclude_label_help,
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
        "--source",
        choices=SEARCH_SOURCE_CHOICES,
        default="auto",
        help="search 可用来源：google、x、x-user、x-news 或 all；默认 auto=google。",
    )
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


def emit_output(format_name: str, sections) -> str:
    if format_name == "json":
        return render_json(sections)
    return render_text(sections)


def semantic_collection_options(args) -> dict[str, object]:
    return {
        "semantic_enabled": not args.no_semantic,
        "semantic_filter": not args.no_semantic and not args.no_filter,
        "excluded_labels": tuple(args.exclude_label) if args.exclude_label else None,
        "semantic_model_dir": args.semantic_model_dir,
        "filter_mode": args.filter_mode,
        "fetch_body": args.fetch_body,
        "body_timeout": args.body_timeout,
        "body_max_chars": args.body_max_chars,
    }
