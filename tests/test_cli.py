from __future__ import annotations

import unittest

from daily_cli.cli import build_parser


class CliParserTests(unittest.TestCase):
    def test_summary_accepts_filter_mode(self) -> None:
        args = build_parser().parse_args(["summary", "--filter-mode", "tfidf"])
        self.assertEqual(args.filter_mode, "tfidf")

    def test_summary_rejects_filter_backend(self) -> None:
        with self.assertRaises(SystemExit):
            build_parser().parse_args(["summary", "--filter-backend", "tfidf"])


if __name__ == "__main__":
    unittest.main()
