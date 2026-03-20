from __future__ import annotations

import argparse
import json

from ..service.topics import list_topics


def register(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    parser = subparsers.add_parser(
        "topics",
        help="列出支持的 topics。",
        description="列出全部 topics、默认来源、默认 limit 和默认过滤标签。",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--format",
        choices=("text", "json"),
        default="text",
        help="输出格式。",
    )
    parser.set_defaults(handler=handle)


def handle(args) -> int:
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
