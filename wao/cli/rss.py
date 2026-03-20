from __future__ import annotations

import argparse
import json
from textwrap import dedent

from ..service.rss import add_subscription, collect_rss, load_subscriptions, pull_saved_rss, remove_subscription
from .args import add_common_fetch_args, emit_output, semantic_collection_options


def register(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    parser = subparsers.add_parser(
        "rss",
        help="统一处理 RSSHub 与普通 RSS/Atom。",
        description=dedent(
            """\
            原子 RSS 能力，支持一次性抓取和持久化订阅管理。

            示例:
              wao rss fetch rsshub://twitter/user/elonmusk
              wao rss fetch https://36kr.com/feed
              wao rss add rsshub://twitter/user/elonmusk --name Elon
              wao rss list
              wao rss pull
            """
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    rss_subparsers = parser.add_subparsers(dest="rss_command", required=True)

    fetch_parser = rss_subparsers.add_parser(
        "fetch",
        help="一次性抓取一条 RSSHub 或 RSS/Atom feed，不写入本地配置。",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    fetch_parser.add_argument(
        "subscription_uri",
        help="订阅地址，例如 rsshub://twitter/user/elonmusk 或 https://36kr.com/feed",
    )
    fetch_parser.add_argument("--name", default=None, help="可读名称；默认使用订阅地址。")
    fetch_parser.add_argument(
        "--instance",
        default=None,
        help="RSSHub 实例地址；默认使用 https://rsshub.app。",
    )
    add_common_fetch_args(
        fetch_parser,
        include_source=False,
        exclude_label_help="追加需要过滤掉的语义标签；rss 默认不自动过滤，传入后才会分类拦截。",
    )
    fetch_parser.set_defaults(handler=handle_fetch)

    add_parser = rss_subparsers.add_parser(
        "add",
        help="新增一条订阅。",
        description="保存一条 RSSHub 或普通 RSS/Atom 订阅。",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    add_parser.add_argument(
        "subscription_uri",
        help="订阅地址，例如 rsshub://twitter/user/elonmusk 或 https://36kr.com/feed",
    )
    add_parser.add_argument("--name", default=None, help="可读名称；默认使用订阅地址。")
    add_parser.add_argument(
        "--instance",
        default=None,
        help="RSSHub 实例地址；默认使用 https://rsshub.app。",
    )
    add_parser.set_defaults(handler=handle_add)

    list_parser = rss_subparsers.add_parser(
        "list",
        help="列出已保存的订阅。",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    list_parser.add_argument(
        "--format",
        choices=("text", "json"),
        default="text",
        help="输出格式。",
    )
    list_parser.set_defaults(handler=handle_list)

    remove_parser = rss_subparsers.add_parser(
        "remove",
        help="删除一条订阅。",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    remove_parser.add_argument("key", help="订阅 key，可通过 `wao rss list` 查看。")
    remove_parser.set_defaults(handler=handle_remove)

    pull_parser = rss_subparsers.add_parser(
        "pull",
        help="拉取已保存的订阅。",
        description="不传 key 时默认拉取全部订阅。",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    pull_parser.add_argument(
        "subscriptions",
        nargs="*",
        help="要拉取的订阅 key；不传时拉取全部。",
    )
    add_common_fetch_args(
        pull_parser,
        include_source=False,
        exclude_label_help="追加需要过滤掉的语义标签；rss 默认不自动过滤，传入后才会分类拦截。",
    )
    pull_parser.set_defaults(handler=handle_pull)


def handle_fetch(args) -> int:
    section = collect_rss(
        args.subscription_uri,
        name=args.name,
        instance=args.instance,
        limit=args.limit,
        timeout=args.timeout,
        **semantic_collection_options(args),
    )
    print(emit_output(args.format, [section]), end="")
    return 0


def handle_add(args) -> int:
    subscription = add_subscription(
        args.subscription_uri,
        name=args.name,
        instance=args.instance,
    )
    print(f"已添加订阅: {subscription.key}")
    print(f"名称: {subscription.label}")
    print(f"地址: {subscription.uri}")
    print(f"实例: {subscription.instance}")
    print(f"路由: {subscription.route}")
    return 0


def handle_list(args) -> int:
    subscriptions = load_subscriptions()
    if args.format == "json":
        payload = {"subscriptions": [item.to_dict() for item in subscriptions]}
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0
    if not subscriptions:
        print("暂无订阅")
        return 0
    for item in subscriptions:
        print(f"{item.key}: {item.label}")
        print(f"  {item.uri}")
        print(f"  instance={item.instance}")
    return 0


def handle_remove(args) -> int:
    removed = remove_subscription(args.key)
    print(f"已删除订阅: {removed.key}")
    return 0


def handle_pull(args) -> int:
    sections = pull_saved_rss(
        args.subscriptions,
        limit=args.limit,
        timeout=args.timeout,
        **semantic_collection_options(args),
    )
    if not sections:
        print("暂无订阅")
        return 0
    print(emit_output(args.format, sections), end="")
    return 0
