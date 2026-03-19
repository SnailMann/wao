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
        self.assertIn("daily summary", help_text)
        self.assertIn("topics", help_text)

    def test_topics_command_exists(self) -> None:
        args = build_parser().parse_args(["topics"])
        self.assertEqual(args.command, "topics")


if __name__ == "__main__":
    unittest.main()
