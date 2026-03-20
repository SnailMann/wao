from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
import re

from ..core.config import config_file, existing_config_file, read_json_file, write_json_file
from ..fetchers.rss import parse_feed_url, parse_rsshub_uri
from ..core.specs import CollectionSpec, SourcePlan, TopicSpec


@dataclass(frozen=True)
class SubscriptionSpec:
    key: str
    name: str
    kind: str
    route: str
    instance: str
    uri: str

    @property
    def label(self) -> str:
        if self.kind == "rsshub":
            return self.name or self.route.lstrip("/")
        return self.name or self.route

    @property
    def feed_url(self) -> str:
        if self.kind == "feed":
            return self.route
        route = self.route if self.route.startswith("/") else f"/{self.route}"
        return f"{self.instance.rstrip('/')}{route}"

    def to_dict(self) -> dict[str, str]:
        return asdict(self)


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.casefold()).strip("-")
    return slug or "rsshub"


def subscriptions_file() -> Path:
    return config_file("subscriptions.json")


def _read_payload() -> list[dict[str, str]]:
    return read_json_file(existing_config_file("subscriptions.json"), default=[])


def _write_payload(items: list[dict[str, str]]) -> None:
    write_json_file(subscriptions_file(), items)


def load_subscriptions() -> list[SubscriptionSpec]:
    items = []
    for payload in _read_payload():
        items.append(SubscriptionSpec(**payload))
    return items


def save_subscriptions(subscriptions: list[SubscriptionSpec]) -> None:
    payload = [item.to_dict() for item in subscriptions]
    _write_payload(payload)


def build_subscription(
    subscription_uri: str,
    *,
    name: str | None = None,
    instance: str | None = None,
) -> SubscriptionSpec:
    if subscription_uri.startswith("rsshub://"):
        route = parse_rsshub_uri(subscription_uri, instance=instance)
        label = (name or route.route.lstrip("/")).strip()
        return SubscriptionSpec(
            key=_slugify(f"{label}-{route.key}"),
            name=label,
            kind="rsshub",
            route=route.route,
            instance=route.instance,
            uri=subscription_uri,
        )

    if instance:
        raise ValueError("普通 RSS/Atom 订阅不需要 --instance")

    feed = parse_feed_url(subscription_uri)
    label = (name or feed.url).strip()
    return SubscriptionSpec(
        key=_slugify(f"{label}-{feed.key}"),
        name=label,
        kind="feed",
        route=feed.url,
        instance="",
        uri=subscription_uri,
    )


def add_subscription(
    subscription_uri: str,
    *,
    name: str | None = None,
    instance: str | None = None,
) -> SubscriptionSpec:
    new_subscription = build_subscription(subscription_uri, name=name, instance=instance)
    subscriptions = load_subscriptions()
    for existing in subscriptions:
        if (
            existing.kind == new_subscription.kind
            and existing.route == new_subscription.route
            and existing.instance == new_subscription.instance
        ):
            raise ValueError(f"订阅已存在: {existing.key}")
    subscriptions.append(new_subscription)
    save_subscriptions(subscriptions)
    return new_subscription


def remove_subscription(key: str) -> SubscriptionSpec:
    subscriptions = load_subscriptions()
    kept: list[SubscriptionSpec] = []
    removed: SubscriptionSpec | None = None
    for item in subscriptions:
        if item.key == key:
            removed = item
            continue
        kept.append(item)
    if removed is None:
        raise ValueError(f"找不到订阅: {key}")
    save_subscriptions(kept)
    return removed


def resolve_subscriptions(keys: list[str] | tuple[str, ...] | None = None) -> list[SubscriptionSpec]:
    subscriptions = load_subscriptions()
    if not keys:
        return subscriptions

    by_key = {item.key: item for item in subscriptions}
    resolved: list[SubscriptionSpec] = []
    missing: list[str] = []
    for key in keys:
        item = by_key.get(key)
        if item is None:
            missing.append(key)
            continue
        resolved.append(item)
    if missing:
        raise ValueError(f"找不到这些订阅: {', '.join(missing)}")
    return resolved


def build_subscription_topic(subscription: SubscriptionSpec) -> TopicSpec:
    if subscription.kind == "feed":
        return CollectionSpec(
            key=subscription.key,
            label=f"订阅: {subscription.label}",
            description=f"RSS/Atom 订阅 {subscription.feed_url}",
            source_plans=(
                SourcePlan(
                    source="feed",
                    mode="url",
                    query=subscription.feed_url,
                ),
            ),
            default_sources=("feed",),
            default_limit=10,
            default_excluded_labels=(),
        )

    return CollectionSpec(
        key=subscription.key,
        label=f"订阅: {subscription.label}",
        description=f"RSSHub 订阅 {subscription.route} ({subscription.instance})",
        source_plans=(
            SourcePlan(
                source="rsshub",
                mode="route",
                query=subscription.route,
                endpoint=subscription.instance,
            ),
        ),
        default_sources=("rsshub",),
        default_limit=10,
        default_excluded_labels=(),
    )


def build_preview_topic(
    subscription_uri: str,
    *,
    name: str | None = None,
    instance: str | None = None,
) -> TopicSpec:
    subscription = build_subscription(subscription_uri, name=name, instance=instance)
    return build_subscription_topic(subscription)
