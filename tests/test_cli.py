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
        self.assertIn("us-hot, china-hot, ai, finance, us-market, github, x", help_text)
        self.assertIn("默认仅 us-hot / china-hot 过滤 soft", help_text)
        self.assertIn("Google News Top Stories 回补", help_text)
        self.assertIn("--filter-mode tfidf|model", help_text)
        self.assertIn("--source auto|google|baidu|github|x|all", help_text)
        self.assertIn("--exclude-label macro|industry|tech|public|soft", help_text)
        self.assertIn("--fetch-body", help_text)
        self.assertIn("daily summary", help_text)
        self.assertIn("topics", help_text)
        self.assertIn("subscriptions", help_text)
        self.assertIn("daily x login", help_text)

    def test_topics_command_exists(self) -> None:
        args = build_parser().parse_args(["topics"])
        self.assertEqual(args.command, "topics")

    def test_subscriptions_preview_accepts_common_fetch_args(self) -> None:
        args = build_parser().parse_args(
            [
                "subscriptions",
                "preview",
                "rsshub://twitter/user/elonmusk",
                "--limit",
                "3",
                "--filter-mode",
                "tfidf",
            ]
        )
        self.assertEqual(args.command, "subscriptions")
        self.assertEqual(args.subscriptions_command, "preview")
        self.assertEqual(args.limit, 3)
        self.assertEqual(args.filter_mode, "tfidf")

    def test_subscriptions_add_accepts_plain_feed_url(self) -> None:
        args = build_parser().parse_args(
            ["subscriptions", "add", "https://36kr.com/feed", "--name", "36kr"]
        )
        self.assertEqual(args.command, "subscriptions")
        self.assertEqual(args.subscriptions_command, "add")
        self.assertEqual(args.subscription_uri, "https://36kr.com/feed")

    def test_fetch_accepts_x_user(self) -> None:
        args = build_parser().parse_args(["fetch", "x", "--x-user", "elonmusk"])
        self.assertEqual(args.command, "fetch")
        self.assertEqual(args.topics, ["x"])
        self.assertEqual(args.x_user, "elonmusk")

    def test_x_login_command_exists(self) -> None:
        args = build_parser().parse_args(["x", "login"])
        self.assertEqual(args.command, "x")
        self.assertEqual(args.x_command, "login")

    def test_x_fetch_accepts_username(self) -> None:
        args = build_parser().parse_args(["x", "fetch", "elonmusk", "--limit", "3"])
        self.assertEqual(args.command, "x")
        self.assertEqual(args.x_command, "fetch")
        self.assertEqual(args.username, "elonmusk")
        self.assertEqual(args.limit, 3)


if __name__ == "__main__":
    unittest.main()
