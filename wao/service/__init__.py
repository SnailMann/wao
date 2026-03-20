"""Service layer: composes fetchers and plugins into query capabilities."""

from .collector import collect_search, collect_summary, collect_topic_specs, collect_topics
from .rss import add_subscription, collect_rss, load_subscriptions, pull_saved_rss, remove_subscription
from .search import SEARCH_DEFAULT_SOURCE, SEARCH_SOURCE_CHOICES, build_search_topic
from .topics import DEFAULT_SUMMARY_TOPICS, list_topic_keys, list_topics
from .trend import TREND_SOURCE_CHOICES, collect_trends, list_trend_specs

__all__ = [
    "SEARCH_DEFAULT_SOURCE",
    "SEARCH_SOURCE_CHOICES",
    "TREND_SOURCE_CHOICES",
    "DEFAULT_SUMMARY_TOPICS",
    "add_subscription",
    "build_search_topic",
    "collect_rss",
    "collect_search",
    "collect_summary",
    "collect_topic_specs",
    "collect_topics",
    "collect_trends",
    "list_topic_keys",
    "list_topics",
    "list_trend_specs",
    "load_subscriptions",
    "pull_saved_rss",
    "remove_subscription",
]
