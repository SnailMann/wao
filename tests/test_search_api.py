from __future__ import annotations

import unittest

from daily_cli.tools.search import SEARCH_SOURCE_CHOICES, build_search_topic


class SearchApiTests(unittest.TestCase):
    def test_public_search_module_exports_x_user_source(self) -> None:
        self.assertIn("x-user", SEARCH_SOURCE_CHOICES)

    def test_build_search_topic_supports_x_user(self) -> None:
        topic = build_search_topic("elonmusk", "us", source="x-user")
        self.assertEqual(topic.key, "search")
        self.assertEqual(topic.supported_sources, ("x-user",))
        self.assertEqual(topic.source_plans[0].mode, "user_posts")
        self.assertEqual(topic.source_plans[0].query, "elonmusk")


if __name__ == "__main__":
    unittest.main()
