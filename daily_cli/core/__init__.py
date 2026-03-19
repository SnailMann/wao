"""Core domain models, topic registry, and orchestration pipeline."""

from .models import NewsItem, SectionResult
from .pipeline import collect_search, collect_summary, collect_topic, collect_topics
from .topics import DEFAULT_SUMMARY_TOPICS, TopicSpec, list_topic_keys, list_topics

__all__ = [
    "DEFAULT_SUMMARY_TOPICS",
    "NewsItem",
    "SectionResult",
    "TopicSpec",
    "collect_search",
    "collect_summary",
    "collect_topic",
    "collect_topics",
    "list_topic_keys",
    "list_topics",
]
