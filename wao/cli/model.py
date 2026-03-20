from __future__ import annotations

import argparse

from ..plugins.semantic import MODEL_REPO_ID, download_model


def register(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    parser = subparsers.add_parser(
        "model",
        help="下载或查看 model 过滤模式所需模型。",
        description="管理 model 过滤模式所需的语义模型文件。",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    model_subparsers = parser.add_subparsers(dest="model_command", required=True)

    download_parser = model_subparsers.add_parser(
        "download",
        help="提前下载 model 模式的语义模型文件。",
        description=(
            f"下载 model 模式使用的语义模型。\n当前模型: {MODEL_REPO_ID}\n"
            "如果你只使用 --filter-mode tfidf，可以不下载。"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    download_parser.add_argument(
        "--model-dir",
        default=None,
        help="模型下载目录；默认使用缓存目录。",
    )
    download_parser.add_argument(
        "--force",
        action="store_true",
        help="强制重新下载模型文件。",
    )
    download_parser.set_defaults(handler=handle_download)


def handle_download(args) -> int:
    model_path = download_model(model_dir=args.model_dir, force=args.force)
    print(f"模型: {MODEL_REPO_ID}")
    print(f"目录: {model_path}")
    print("状态: 已下载，可直接用于 summary/fetch/search")
    return 0
