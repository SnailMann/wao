"""Core domain models, topic registry, and orchestration pipeline."""

from .models import NewsItem, SectionResult
from .pipeline import collect_search, collect_summary, collect_topic, collect_topic_specs, collect_topics
from .subscriptions import (
    SubscriptionSpec,
    add_subscription,
    build_subscription_topic,
    build_preview_topic,
    load_subscriptions,
    remove_subscription,
    resolve_subscriptions,
)
from .topics import DEFAULT_SUMMARY_TOPICS, TopicSpec, build_x_topic, list_topic_keys, list_topics

__all__ = [
    "DEFAULT_SUMMARY_TOPICS",
    "NewsItem",
    "SectionResult",
    "SubscriptionSpec",
    "add_subscription",
    "build_preview_topic",
    "build_subscription_topic",
    "TopicSpec",
    "build_x_topic",
    "collect_search",
    "collect_summary",
    "collect_topic",
    "collect_topic_specs",
    "collect_topics",
    "load_subscriptions",
    "list_topic_keys",
    "list_topics",
    "remove_subscription",
    "resolve_subscriptions",
]
