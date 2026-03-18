from __future__ import annotations

import unittest
from unittest.mock import patch

from daily_cli.models import NewsItem, SectionResult
from daily_cli.service import _apply_semantic_controls


class StubLabeler:
    def annotate_items(self, items: list[NewsItem]) -> list[NewsItem]:
        for item in items:
            if "蹭饭" in item.title:
                item.content_label = "soft"
                item.content_label_name = "低信息量"
                item.content_label_score = 0.91
            else:
                item.content_label = "macro"
                item.content_label_name = "宏观与政策"
                item.content_label_score = 0.84
        return items


def make_section(items: list[NewsItem]) -> SectionResult:
    return SectionResult(
        key="china-hot",
        label="中国热门事件",
        requested_source="baidu",
        resolved_sources=["baidu"],
        generated_at="2026-03-18 22:00:00 CST",
        items=items,
    )


class SemanticFilterTests(unittest.TestCase):
    @patch("daily_cli.service.get_semantic_labeler", return_value=StubLabeler())
    def test_default_soft_filter_removes_low_signal_items(self, _mocked_labeler) -> None:
        section = make_section(
            [
                NewsItem(title="男子买车一年蹭饭260次还打包", category="china-hot", provider="baidu", feed="Baidu Hotboard"),
                NewsItem(title="美联储暗示年内或继续降息", category="china-hot", provider="baidu", feed="Baidu Hotboard"),
            ]
        )

        result = _apply_semantic_controls(
            section,
            default_excluded_labels=("soft",),
            final_limit=5,
            semantic_enabled=True,
            semantic_filter=True,
            excluded_labels=None,
            semantic_model_dir=None,
        )

        self.assertTrue(result.semantic_enabled)
        self.assertTrue(result.filter_enabled)
        self.assertEqual(result.excluded_labels, ["soft"])
        self.assertEqual(result.filtered_count, 1)
        self.assertEqual(len(result.items), 1)
        self.assertEqual(result.items[0].title, "美联储暗示年内或继续降息")
        self.assertEqual(result.items[0].content_label, "macro")

    @patch("daily_cli.service.get_semantic_labeler", return_value=StubLabeler())
    def test_custom_excluded_labels_override_default_soft_filter(self, _mocked_labeler) -> None:
        section = make_section(
            [
                NewsItem(title="男子买车一年蹭饭260次还打包", category="china-hot", provider="baidu", feed="Baidu Hotboard"),
                NewsItem(title="城市更新计划推进老旧社区改造", category="china-hot", provider="baidu", feed="Baidu Hotboard"),
            ]
        )

        result = _apply_semantic_controls(
            section,
            default_excluded_labels=("soft",),
            final_limit=5,
            semantic_enabled=True,
            semantic_filter=True,
            excluded_labels=("public",),
            semantic_model_dir=None,
        )

        self.assertEqual(result.excluded_labels, ["public"])
        self.assertEqual(result.filtered_count, 0)
        self.assertEqual(len(result.items), 2)
        self.assertEqual(result.items[0].content_label, "soft")


if __name__ == "__main__":
    unittest.main()
