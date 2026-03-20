from __future__ import annotations

import unittest

from daily_cli.cli import build_parser


class CliParserTests(unittest.TestCase):
    def test_summary_accepts_filter_mode(self) -> None:
        args = build_parser().parse_args(["summary", "--filter-mode", "tfidf"])
        self.assertEqual(args.filter_mode, "tfidf")

    def test_fetch_accepts_body_fetch_options(self) -> None:
        args = build_parser().parse_args(
            ["fetch", "us-hot", "--fetch-body", "--body-timeout", "12", "--body-max-chars", "1234"]
        )
        self.assertTrue(args.fetch_body)
        self.assertEqual(args.body_timeout, 12.0)
        self.assertEqual(args.body_max_chars, 1234)
        self.assertEqual(args.topics, ["us-hot"])

    def test_summary_rejects_filter_backend(self) -> None:
        with self.assertRaises(SystemExit):
            build_parser().parse_args(["summary", "--filter-backend", "tfidf"])

    def test_top_level_help_mentions_topics_and_daily_command(self) -> None:
        help_text = build_parser().format_help()
        self.assertIn("us-hot, china-hot, ai, finance, us-market, github", help_text)
        self.assertIn("默认仅 us-hot / china-hot 过滤 soft", help_text)
        self.assertIn("Google News Top Stories 回补", help_text)
        self.assertIn("--filter-mode tfidf|model", help_text)
        self.assertIn("--source auto|google|baidu|github|all", help_text)
        self.assertIn("--exclude-label macro|industry|tech|public|soft", help_text)
        self.assertIn("--fetch-body", help_text)
        self.assertIn("trend", help_text)
        self.assertIn("rss", help_text)
        self.assertIn("daily summary", help_text)
        self.assertIn("topics", help_text)
        self.assertIn("daily x login", help_text)
        self.assertIn("daily trend", help_text)
        self.assertIn("daily rss fetch https://36kr.com/feed", help_text)
        self.assertIn("daily search \"OpenAI\" --source x", help_text)
        self.assertIn("daily search elonmusk --source x-user", help_text)
        self.assertNotIn("daily x fetch", help_text)

    def test_topics_command_exists(self) -> None:
        args = build_parser().parse_args(["topics"])
        self.assertEqual(args.command, "topics")

    def test_trend_accepts_source(self) -> None:
        args = build_parser().parse_args(["trend", "--source", "baidu", "--limit", "3"])
        self.assertEqual(args.command, "trend")
        self.assertEqual(args.source, "baidu")
        self.assertEqual(args.limit, 3)

    def test_rss_fetch_accepts_common_fetch_args(self) -> None:
        args = build_parser().parse_args(
            [
                "rss",
                "fetch",
                "rsshub://twitter/user/elonmusk",
                "--limit",
                "3",
                "--filter-mode",
                "tfidf",
            ]
        )
        self.assertEqual(args.command, "rss")
        self.assertEqual(args.rss_command, "fetch")
        self.assertEqual(args.limit, 3)
        self.assertEqual(args.filter_mode, "tfidf")

    def test_rss_add_accepts_plain_feed_url(self) -> None:
        args = build_parser().parse_args(
            ["rss", "add", "https://36kr.com/feed", "--name", "36kr"]
        )
        self.assertEqual(args.command, "rss")
        self.assertEqual(args.rss_command, "add")
        self.assertEqual(args.subscription_uri, "https://36kr.com/feed")

    def test_x_login_command_exists(self) -> None:
        args = build_parser().parse_args(["x", "login"])
        self.assertEqual(args.command, "x")
        self.assertEqual(args.x_command, "login")

    def test_search_accepts_x_source(self) -> None:
        args = build_parser().parse_args(["search", "OpenAI", "--source", "x-news"])
        self.assertEqual(args.command, "search")
        self.assertEqual(args.source, "x-news")

    def test_search_accepts_x_user_source(self) -> None:
        args = build_parser().parse_args(["search", "elonmusk", "--source", "x-user"])
        self.assertEqual(args.command, "search")
        self.assertEqual(args.source, "x-user")

    def test_fetch_rejects_removed_x_topic(self) -> None:
        with self.assertRaises(SystemExit):
            build_parser().parse_args(["fetch", "x"])


if __name__ == "__main__":
    unittest.main()
