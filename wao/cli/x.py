from __future__ import annotations

import argparse
import getpass
from textwrap import dedent

from ..core.x_auth import (
    clear_saved_x_bearer_token,
    resolve_x_bearer_token,
    save_x_bearer_token,
    x_token_file,
)
from ..fetchers.common import FetchError
from ..fetchers.x import fetch_x_usage


def register(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    parser = subparsers.add_parser(
        "x",
        help="配置或查看 X Bearer Token。",
        description=dedent(
            """\
            管理 X 官方 API 所需的 Bearer Token。

            示例:
              wao x login
              wao x login <BEARER_TOKEN>
              wao x status
              wao x logout
              wao search elonmusk --source x-user
              wao search "OpenAI" --source x
            """
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    x_subparsers = parser.add_subparsers(dest="x_command", required=True)

    login_parser = x_subparsers.add_parser(
        "login",
        help="保存 X Bearer Token。",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    login_parser.add_argument(
        "token",
        nargs="?",
        help="X Bearer Token；不传时会在终端里安全输入。",
    )
    login_parser.set_defaults(handler=handle_login)

    status_parser = x_subparsers.add_parser(
        "status",
        help="查看当前 X Token 配置状态。",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    status_parser.set_defaults(handler=handle_status)

    logout_parser = x_subparsers.add_parser(
        "logout",
        help="删除本地保存的 X Token。",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    logout_parser.set_defaults(handler=handle_logout)


def handle_login(args) -> int:
    token = (args.token or "").strip()
    if not token:
        token = getpass.getpass("X Bearer Token: ").strip()
    state = save_x_bearer_token(token)
    print("X Token 已保存")
    print(f"来源: {state.source}")
    print(f"路径: {state.path}")
    print(f"Token: {state.masked_token}")
    return 0


def handle_status(args) -> int:
    try:
        state = resolve_x_bearer_token()
    except ValueError as exc:
        if "未配置 X Bearer Token" not in str(exc):
            raise
        path = x_token_file()
        print("X Token: 未配置")
        print("建议: 运行 `wao x login`，或设置环境变量 X_BEARER_TOKEN")
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


def handle_logout(args) -> int:
    removed = clear_saved_x_bearer_token()
    if removed:
        print("本地 X Token 已删除")
    else:
        print("本地没有保存的 X Token")
    print(f"路径: {x_token_file()}")
    return 0
