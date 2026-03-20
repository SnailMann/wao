from __future__ import annotations

import os
import tempfile
import unittest
from unittest.mock import patch

from daily_cli.core.subscriptions import (
    add_subscription,
    build_preview_topic,
    build_subscription_topic,
    load_subscriptions,
    remove_subscription,
)
from daily_cli.runtime.rsshub import parse_feed_url, parse_generic_feed, parse_rsshub_uri


RSSHUB_SAMPLE = """\
<rss version="2.0">
  <channel>
    <title>Twitter @elonmusk</title>
    <item>
      <title>Starship flight update</title>
      <link>https://x.com/elonmusk/status/1</link>
      <description><![CDATA[Launch window moved to Friday.]]></description>
      <pubDate>Wed, 19 Mar 2026 08:00:00 GMT</pubDate>
      <author>Elon Musk</author>
    </item>
    <item>
      <title>SpaceX factory update</title>
      <link>https://x.com/elonmusk/status/2</link>
      <description><![CDATA[New production line is online.]]></description>
      <pubDate>Wed, 19 Mar 2026 07:00:00 GMT</pubDate>
      <author>Elon Musk</author>
    </item>
  </channel>
</rss>
"""


class RSSHubTests(unittest.TestCase):
    def test_parse_rsshub_uri(self) -> None:
        route = parse_rsshub_uri("rsshub://twitter/user/elonmusk")

        self.assertEqual(route.route, "/twitter/user/elonmusk")
        self.assertEqual(route.instance, "https://rsshub.app")
        self.assertEqual(route.feed_url, "https://rsshub.app/twitter/user/elonmusk")

    def test_parse_plain_feed_url(self) -> None:
        feed = parse_feed_url("https://36kr.com/feed")

        self.assertEqual(feed.url, "https://36kr.com/feed")
        self.assertTrue(feed.key.startswith("36kr.com-feed-"))

    def test_parse_generic_feed(self) -> None:
        feed_name, items = parse_generic_feed(
            RSSHUB_SAMPLE,
            limit=2,
            category="subscription",
            provider="rsshub",
            default_feed_name="RSSHub",
        )

        self.assertEqual(feed_name, "Twitter @elonmusk")
        self.assertEqual(len(items), 2)
        self.assertEqual(items[0].title, "Starship flight update")
        self.assertEqual(items[0].publisher, "Elon Musk")
        self.assertEqual(items[0].feed, "Twitter @elonmusk")

    def test_add_and_remove_subscription(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch.dict(os.environ, {"XDG_CONFIG_HOME": temp_dir}, clear=False):
                subscription = add_subscription(
                    "rsshub://twitter/user/elonmusk",
                    name="Elon",
                    instance="https://rsshub.app",
                )

                loaded = load_subscriptions()
                self.assertEqual(len(loaded), 1)
                self.assertEqual(loaded[0].key, subscription.key)
                self.assertEqual(loaded[0].label, "Elon")

                removed = remove_subscription(subscription.key)
                self.assertEqual(removed.key, subscription.key)
                self.assertEqual(load_subscriptions(), [])

    def test_build_subscription_topic_uses_rsshub_provider(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch.dict(os.environ, {"XDG_CONFIG_HOME": temp_dir}, clear=False):
                subscription = add_subscription(
                    "rsshub://twitter/user/elonmusk",
                    name="Elon",
                    instance="https://rsshub.app",
                )
                topic = build_subscription_topic(subscription)

        self.assertEqual(topic.default_sources, ("rsshub",))
        self.assertEqual(topic.source_plans[0].source, "rsshub")
        self.assertEqual(topic.source_plans[0].mode, "route")
        self.assertEqual(topic.source_plans[0].query, "/twitter/user/elonmusk")

    def test_add_plain_feed_subscription(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch.dict(os.environ, {"XDG_CONFIG_HOME": temp_dir}, clear=False):
                subscription = add_subscription(
                    "https://36kr.com/feed",
                    name="36kr",
                )
                loaded = load_subscriptions()

        self.assertEqual(subscription.kind, "feed")
        self.assertEqual(subscription.feed_url, "https://36kr.com/feed")
        self.assertEqual(loaded[0].kind, "feed")
        self.assertEqual(loaded[0].label, "36kr")

    def test_build_plain_feed_subscription_topic_uses_feed_provider(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch.dict(os.environ, {"XDG_CONFIG_HOME": temp_dir}, clear=False):
                subscription = add_subscription(
                    "https://36kr.com/feed",
                    name="36kr",
                )
                topic = build_subscription_topic(subscription)

        self.assertEqual(topic.default_sources, ("feed",))
        self.assertEqual(topic.source_plans[0].source, "feed")
        self.assertEqual(topic.source_plans[0].mode, "url")
        self.assertEqual(topic.source_plans[0].query, "https://36kr.com/feed")

    def test_build_preview_topic_supports_plain_feed(self) -> None:
        topic = build_preview_topic("https://36kr.com/feed", name="36kr")

        self.assertEqual(topic.source_plans[0].source, "feed")
        self.assertEqual(topic.label, "订阅: 36kr")


if __name__ == "__main__":
    unittest.main()
