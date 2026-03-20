from __future__ import annotations

import argparse
import getpass
import json
from textwrap import dedent

from . import __version__
from .core.pipeline import collect_search, collect_summary, collect_topic_specs
from .core.x_auth import (
    clear_saved_x_bearer_token,
    resolve_x_bearer_token,
    save_x_bearer_token,
    x_token_file,
)
from .core.subscriptions import (
    add_subscription,
    build_preview_topic,
    build_subscription_topic,
    load_subscriptions,
    remove_subscription,
    resolve_subscriptions,
)
from .core.topics import DEFAULT_SUMMARY_TOPICS, build_x_topic, get_topic, list_topic_keys, list_topics
from .plugins.filters import list_filter_modes
from .renderers.output import render_json, render_text
from .runtime.semantic import MODEL_REPO_ID, SemanticError, download_model, list_content_labels
from .runtime.sources import FetchError
from .runtime.x_api import fetch_x_usage


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
          一个面向 Linux / macOS 的资讯命令行工具，聚合 Google、Baidu、GitHub 和 X 的公开信息源。

        Commands:
          topics
            列出全部 topic、默认来源、默认数量和默认过滤策略。
          x
            配置 X Bearer Token，或直接拉取某个公开账号的最近发推。
          subscriptions
            管理 RSSHub 与普通 RSS/Atom 订阅，支持 add/list/fetch/remove/preview。
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
          --source auto|google|baidu|github|x|all
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
          ai / finance / us-market / github / x / search 默认只抓取，不自动分类。
          us-hot 过滤后不足时，会按需用 Google News Top Stories 回补。

        Examples:
          daily summary
          daily summary --filter-mode tfidf --limit 5
          daily x login
          daily x fetch elonmusk
          daily fetch x --x-user elonmusk
          daily subscriptions add rsshub://twitter/user/elonmusk --name Elon
          daily subscriptions add https://36kr.com/feed --name 36kr
          daily subscriptions fetch
          daily fetch us-hot china-hot --exclude-label soft
          daily fetch github --limit 10 --format json
          daily fetch us-hot --fetch-body --body-max-chars 3000
          daily search "人工智能" --google-locale cn
          daily model download

        More:
          运行 `daily <command> --help` 查看某个命令的详细参数。
        """
    )


def add_common_fetch_args(parser: argparse.ArgumentParser, *, include_source: bool = True) -> None:
    if include_source:
        parser.add_argument(
            "--source",
            choices=("auto", "google", "baidu", "github", "x", "all"),
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


def _resolve_fetch_specs(keys: list[str] | tuple[str, ...], *, x_user: str | None) -> list:
    specs = []
    has_x = False
    for key in keys:
        if key == "x":
            has_x = True
            specs.append(build_x_topic(x_user or ""))
            continue
        specs.append(get_topic(key))
    if x_user and not has_x:
        raise ValueError("`--x-user` 仅在 `fetch x` 时使用")
    return specs


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="daily",
        description="快速检索每日热门话题、专题资讯、GitHub Trending 与 X 用户动态。",
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

    x_parser = subparsers.add_parser(
        "x",
        help="配置 X Bearer Token，或拉取某个用户的公开发推。",
        description=dedent(
            """\
            管理 X 官方 API 所需的 Bearer Token，并支持按用户名拉取公开发推。

            示例:
              daily x login
              daily x login <BEARER_TOKEN>
              daily x status
              daily x fetch elonmusk
              daily fetch x --x-user elonmusk
            """
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    x_subparsers = x_parser.add_subparsers(dest="x_command", required=True)

    x_login_parser = x_subparsers.add_parser(
        "login",
        help="保存 X Bearer Token。",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    x_login_parser.add_argument(
        "token",
        nargs="?",
        help="X Bearer Token；不传时会在终端里安全输入。",
    )

    x_subparsers.add_parser(
        "status",
        help="查看当前 X Token 配置状态。",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    x_subparsers.add_parser(
        "logout",
        help="删除本地保存的 X Token。",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    x_fetch_parser = x_subparsers.add_parser(
        "fetch",
        help="按用户名拉取公开发推。",
        description="通过 X 官方 API v2 拉取指定用户名最近公开发推。",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    x_fetch_parser.add_argument("username", help="X 用户名，例如 elonmusk 或 @elonmusk。")
    add_common_fetch_args(x_fetch_parser, include_source=False)

    subscriptions_parser = subparsers.add_parser(
        "subscriptions",
        help="管理 RSSHub 与普通 RSS/Atom 订阅。",
        description=dedent(
            """\
            管理 RSSHub 与普通 RSS/Atom 订阅。

            示例:
              daily subscriptions add rsshub://twitter/user/elonmusk --name Elon
              daily subscriptions add https://36kr.com/feed --name 36kr
              daily subscriptions list
              daily subscriptions fetch
              daily subscriptions preview rsshub://twitter/user/elonmusk
            """
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    subscriptions_subparsers = subscriptions_parser.add_subparsers(
        dest="subscriptions_command",
        required=True,
    )

    subscriptions_add_parser = subscriptions_subparsers.add_parser(
        "add",
        help="新增一条订阅。",
        description="保存一条 RSSHub 或普通 RSS/Atom 订阅。",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    subscriptions_add_parser.add_argument(
        "subscription_uri",
        help="订阅地址，例如 rsshub://twitter/user/elonmusk 或 https://36kr.com/feed",
    )
    subscriptions_add_parser.add_argument("--name", default=None, help="可读名称；默认使用订阅地址。")
    subscriptions_add_parser.add_argument(
        "--instance",
        default=None,
        help="RSSHub 实例地址；默认使用 https://rsshub.app。",
    )

    subscriptions_list_parser = subscriptions_subparsers.add_parser(
        "list",
        help="列出已保存的订阅。",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    subscriptions_list_parser.add_argument(
        "--format",
        choices=("text", "json"),
        default="text",
        help="输出格式。",
    )

    subscriptions_remove_parser = subscriptions_subparsers.add_parser(
        "remove",
        help="删除一条订阅。",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    subscriptions_remove_parser.add_argument("key", help="订阅 key，可通过 `daily subscriptions list` 查看。")

    subscriptions_fetch_parser = subscriptions_subparsers.add_parser(
        "fetch",
        help="拉取已保存的订阅。",
        description="不传 key 时默认拉取全部订阅。",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    subscriptions_fetch_parser.add_argument(
        "subscriptions",
        nargs="*",
        help="要拉取的订阅 key；不传时拉取全部。",
    )
    add_common_fetch_args(subscriptions_fetch_parser, include_source=False)

    subscriptions_preview_parser = subscriptions_subparsers.add_parser(
        "preview",
        help="预览一条订阅，不写入本地配置。",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    subscriptions_preview_parser.add_argument(
        "subscription_uri",
        help="订阅地址，例如 rsshub://twitter/user/elonmusk 或 https://36kr.com/feed",
    )
    subscriptions_preview_parser.add_argument("--name", default=None, help="可读名称；默认使用订阅地址。")
    subscriptions_preview_parser.add_argument(
        "--instance",
        default=None,
        help="RSSHub 实例地址；默认使用 https://rsshub.app。",
    )
    add_common_fetch_args(subscriptions_preview_parser, include_source=False)

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
            若 topic 为 x，需要同时传入 --x-user。
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
    fetch_parser.add_argument(
        "--x-user",
        default=None,
        help="当 topic 包含 x 时，指定要抓取的 X 用户名，例如 elonmusk。",
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

        if args.command == "x":
            if args.x_command == "login":
                token = (args.token or "").strip()
                if not token:
                    token = getpass.getpass("X Bearer Token: ").strip()
                state = save_x_bearer_token(token)
                print("X Token 已保存")
                print(f"来源: {state.source}")
                print(f"路径: {state.path}")
                print(f"Token: {state.masked_token}")
                return 0

            if args.x_command == "status":
                try:
                    state = resolve_x_bearer_token()
                except ValueError as exc:
                    if "未配置 X Bearer Token" not in str(exc):
                        raise
                    path = x_token_file()
                    print("X Token: 未配置")
                    print(f"建议: 运行 `daily x login`，或设置环境变量 X_BEARER_TOKEN")
                    print(f"本地路径: {path}")
                    return 0

                print("X Token: 已配置")
                print(f"来源: {state.source}")
                if state.path:
                    print(f"路径: {state.path}")
                else:
                    print(f"本地路径: {x_token_file()}")
                print(f"Token: {state.masked_token}")
                try:
                    usage = fetch_x_usage(timeout=10.0)
                except FetchError as exc:
                    print(f"Usage: 获取失败 ({exc})")
                else:
                    project_usage = str(usage.get("project_usage") or "")
                    project_cap = str(usage.get("project_cap") or "")
                    cap_reset_day = str(usage.get("cap_reset_day") or "")
                    if project_usage or project_cap:
                        print(f"Usage: {project_usage or '?'} / {project_cap or '?'}")
                    if cap_reset_day:
                        print(f"Reset Day: 每月 {cap_reset_day} 号")
                return 0

            if args.x_command == "logout":
                removed = clear_saved_x_bearer_token()
                if removed:
                    print("本地 X Token 已删除")
                else:
                    print("本地没有保存的 X Token")
                print(f"路径: {x_token_file()}")
                return 0

            if args.x_command == "fetch":
                section = collect_topic_specs(
                    [build_x_topic(args.username)],
                    source="x",
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
                )[0]
                print(emit_output(args.format, [section]), end="")
                return 0

        if args.command == "subscriptions":
            if args.subscriptions_command == "add":
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

            if args.subscriptions_command == "list":
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

            if args.subscriptions_command == "remove":
                removed = remove_subscription(args.key)
                print(f"已删除订阅: {removed.key}")
                return 0

            if args.subscriptions_command == "fetch":
                subscriptions = resolve_subscriptions(args.subscriptions)
                if not subscriptions:
                    print("暂无订阅")
                    return 0
                sections = collect_topic_specs(
                    [build_subscription_topic(item) for item in subscriptions],
                    source="auto",
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

            if args.subscriptions_command == "preview":
                section = collect_topic_specs(
                    [
                        build_preview_topic(
                            args.subscription_uri,
                            name=args.name,
                            instance=args.instance,
                        )
                    ],
                    source="auto",
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
                )[0]
                print(emit_output(args.format, [section]), end="")
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
            sections = collect_topic_specs(
                _resolve_fetch_specs(args.topics, x_user=args.x_user),
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
