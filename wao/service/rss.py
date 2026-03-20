from __future__ import annotations

"""Service-level RSS capability and saved subscription management."""

from .collector import collect_topic_specs
from .subscriptions import (
    SubscriptionSpec,
    add_subscription,
    build_preview_topic,
    build_subscription_topic,
    load_subscriptions,
    remove_subscription,
    resolve_subscriptions,
)


def collect_rss(
    subscription_uri: str,
    *,
    name: str | None = None,
    instance: str | None = None,
    limit: int | None,
    timeout: float,
    semantic_enabled: bool = True,
    semantic_filter: bool = True,
    excluded_labels: tuple[str, ...] | None = None,
    semantic_model_dir: str | None = None,
    filter_mode: str = "tfidf",
    fetch_body: bool = False,
    body_timeout: float = 15.0,
    body_max_chars: int = 4000,
):
    spec = build_preview_topic(subscription_uri, name=name, instance=instance)
    return collect_topic_specs(
        [spec],
        source="auto",
        limit=limit,
        timeout=timeout,
        semantic_enabled=semantic_enabled,
        semantic_filter=semantic_filter,
        excluded_labels=excluded_labels,
        semantic_model_dir=semantic_model_dir,
        filter_mode=filter_mode,
        fetch_body=fetch_body,
        body_timeout=body_timeout,
        body_max_chars=body_max_chars,
    )[0]


def pull_saved_rss(
    keys: list[str] | tuple[str, ...] | None,
    *,
    limit: int | None,
    timeout: float,
    semantic_enabled: bool = True,
    semantic_filter: bool = True,
    excluded_labels: tuple[str, ...] | None = None,
    semantic_model_dir: str | None = None,
    filter_mode: str = "tfidf",
    fetch_body: bool = False,
    body_timeout: float = 15.0,
    body_max_chars: int = 4000,
):
    subscriptions = resolve_subscriptions(keys)
    specs = [build_subscription_topic(item) for item in subscriptions]
    return collect_topic_specs(
        specs,
        source="auto",
        limit=limit,
        timeout=timeout,
        semantic_enabled=semantic_enabled,
        semantic_filter=semantic_filter,
        excluded_labels=excluded_labels,
        semantic_model_dir=semantic_model_dir,
        filter_mode=filter_mode,
        fetch_body=fetch_body,
        body_timeout=body_timeout,
        body_max_chars=body_max_chars,
    )


__all__ = [
    "SubscriptionSpec",
    "add_subscription",
    "collect_rss",
    "load_subscriptions",
    "pull_saved_rss",
    "remove_subscription",
    "resolve_subscriptions",
]
