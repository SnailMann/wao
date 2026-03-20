from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from wao.core.x_auth import (
    clear_saved_x_bearer_token,
    load_saved_x_bearer_token,
    resolve_x_bearer_token,
    save_x_bearer_token,
    x_token_file,
)
from wao.fetchers.x import fetch_x_news_search, fetch_x_recent_search, fetch_x_user_tweets


class XAuthTests(unittest.TestCase):
    def test_save_and_resolve_saved_x_token(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            with patch.dict("os.environ", {"XDG_CONFIG_HOME": tempdir}, clear=False):
                state = save_x_bearer_token("bearer-token-123456")
                self.assertEqual(state.source, "config")
                self.assertTrue(Path(state.path).exists())

                loaded = load_saved_x_bearer_token()
                self.assertIsNotNone(loaded)
                self.assertEqual(loaded.token, "bearer-token-123456")

                resolved = resolve_x_bearer_token()
                self.assertEqual(resolved.token, "bearer-token-123456")
                self.assertEqual(Path(resolved.path), x_token_file())

                self.assertTrue(clear_saved_x_bearer_token())
                self.assertIsNone(load_saved_x_bearer_token())

    def test_resolve_x_token_prefers_env(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            with patch.dict(
                "os.environ",
                {"XDG_CONFIG_HOME": tempdir, "X_BEARER_TOKEN": "env-token-abcdef"},
                clear=False,
            ):
                save_x_bearer_token("saved-token-123456")
                resolved = resolve_x_bearer_token()
                self.assertEqual(resolved.token, "env-token-abcdef")
                self.assertEqual(resolved.source, "env:X_BEARER_TOKEN")


class XApiTests(unittest.TestCase):
    @patch("wao.fetchers.x._fetch_x_json")
    def test_fetch_x_user_tweets(self, mocked_fetch_x_json) -> None:
        mocked_fetch_x_json.side_effect = [
            {
                "data": {
                    "id": "44196397",
                    "name": "Elon Musk",
                    "username": "elonmusk",
                }
            },
            {
                "data": [
                    {
                        "id": "1900000000000000001",
                        "text": "Starship update: next integrated flight test window opens soon.",
                        "created_at": "2026-03-19T02:30:00.000Z",
                        "lang": "en",
                        "public_metrics": {
                            "like_count": 120,
                            "retweet_count": 34,
                            "reply_count": 12,
                            "quote_count": 5,
                        },
                    }
                ]
            },
        ]

        items = fetch_x_user_tweets("elonmusk", limit=5, timeout=5.0, category="x")

        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].provider, "x")
        self.assertEqual(items[0].feed, "X")
        self.assertEqual(items[0].publisher, "Elon Musk (@elonmusk)")
        self.assertEqual(items[0].link, "https://x.com/elonmusk/status/1900000000000000001")
        self.assertEqual(items[0].published_at, "2026-03-19 10:30:00 CST")
        self.assertEqual(items[0].language, "en")
        self.assertIn("赞 120", items[0].tags)
        self.assertIn("Starship update", items[0].title)

    @patch("wao.fetchers.x._fetch_x_json")
    def test_fetch_x_recent_search(self, mocked_fetch_x_json) -> None:
        mocked_fetch_x_json.return_value = {
            "data": [
                {
                    "id": "1900000000000000020",
                    "text": "OpenAI ships a new multimodal release today.",
                    "created_at": "2026-03-20T02:30:00.000Z",
                    "lang": "en",
                    "author_id": "123",
                    "public_metrics": {
                        "like_count": 88,
                        "retweet_count": 21,
                        "reply_count": 9,
                        "quote_count": 3,
                    },
                }
            ],
            "includes": {
                "users": [
                    {
                        "id": "123",
                        "name": "X Dev",
                        "username": "xdev",
                    }
                ]
            },
        }

        items = fetch_x_recent_search("OpenAI", limit=5, timeout=5.0, category="search")

        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].feed, "X Search")
        self.assertEqual(items[0].publisher, "X Dev (@xdev)")
        self.assertEqual(items[0].search_query, "OpenAI")
        self.assertIn("/status/1900000000000000020", items[0].link)

    @patch("wao.fetchers.x._fetch_x_json")
    def test_fetch_x_news_search(self, mocked_fetch_x_json) -> None:
        mocked_fetch_x_json.return_value = {
            "data": [
                {
                    "id": "news-1",
                    "name": "OpenAI unveils new reasoning system",
                    "summary": "A new release was announced at a live event.",
                    "category": "Technology",
                    "updated_at": "2026-03-20T04:30:00.000Z",
                }
            ]
        }

        items = fetch_x_news_search("OpenAI", limit=5, timeout=5.0, category="search")

        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].provider, "x-news")
        self.assertEqual(items[0].feed, "X News")
        self.assertEqual(items[0].title, "OpenAI unveils new reasoning system")
        self.assertIn("Technology", items[0].tags)
        self.assertEqual(items[0].search_query, "OpenAI")
