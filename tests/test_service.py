from __future__ import annotations

import unittest
from unittest.mock import patch

from daily_cli.models import NewsItem, SectionResult
from daily_cli.service import _finalize_section, collect_presets


class StubLabeler:
    def __init__(self) -> None:
        self.calls: list[int] = []

    def annotate_items(self, items: list[NewsItem]) -> list[NewsItem]:
        self.calls.append(len(items))
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
    @patch("daily_cli.service.get_semantic_labeler")
    def test_default_soft_filter_removes_low_signal_items(self, mocked_labeler) -> None:
        mocked_labeler.return_value = StubLabeler()
        section = make_section(
            [
                NewsItem(title="男子买车一年蹭饭260次还打包", category="china-hot", provider="baidu", feed="Baidu Hotboard"),
                NewsItem(title="美联储暗示年内或继续降息", category="china-hot", provider="baidu", feed="Baidu Hotboard"),
            ]
        )

        prepared = type(
            "Prepared",
            (),
            {
                "spec": type("Spec", (), {"default_excluded_labels": ("soft",)})(),
                "final_limit": 5,
            },
        )()

        mocked_labeler.return_value.annotate_items(section.items)
        result = _finalize_section(
            prepared,
            section,
            semantic_enabled=True,
            semantic_filter=True,
            excluded_labels=None,
        )

        self.assertTrue(result.semantic_enabled)
        self.assertTrue(result.filter_enabled)
        self.assertEqual(result.excluded_labels, ["soft"])
        self.assertEqual(result.filtered_count, 1)
        self.assertEqual(len(result.items), 1)
        self.assertEqual(result.items[0].title, "美联储暗示年内或继续降息")
        self.assertEqual(result.items[0].content_label, "macro")

    @patch("daily_cli.service.get_semantic_labeler")
    def test_custom_excluded_labels_override_default_soft_filter(self, mocked_labeler) -> None:
        mocked_labeler.return_value = StubLabeler()
        section = make_section(
            [
                NewsItem(title="男子买车一年蹭饭260次还打包", category="china-hot", provider="baidu", feed="Baidu Hotboard"),
                NewsItem(title="城市更新计划推进老旧社区改造", category="china-hot", provider="baidu", feed="Baidu Hotboard"),
            ]
        )

        prepared = type(
            "Prepared",
            (),
            {
                "spec": type("Spec", (), {"default_excluded_labels": ("soft",)})(),
                "final_limit": 5,
            },
        )()

        mocked_labeler.return_value.annotate_items(section.items)
        result = _finalize_section(
            prepared,
            section,
            semantic_enabled=True,
            semantic_filter=True,
            excluded_labels=("public",),
        )

        self.assertEqual(result.excluded_labels, ["public"])
        self.assertEqual(result.filtered_count, 0)
        self.assertEqual(len(result.items), 2)
        self.assertEqual(result.items[0].content_label, "soft")

    @patch("daily_cli.service.fetch_baidu_realtime")
    @patch("daily_cli.service.fetch_google_trends_us")
    @patch("daily_cli.service.get_semantic_labeler")
    def test_collect_presets_uses_single_global_annotation_batch(
        self,
        mocked_labeler,
        mocked_google_trends,
        mocked_baidu,
    ) -> None:
        labeler = StubLabeler()
        mocked_labeler.return_value = labeler
        mocked_google_trends.return_value = [
            NewsItem(title="Federal Reserve signals more cuts", category="us-hot", provider="google", feed="Google Trends")
        ]
        mocked_baidu.return_value = [
            NewsItem(title="男子买车一年蹭饭260次还打包", category="china-hot", provider="baidu", feed="Baidu Hotboard")
        ]

        sections = collect_presets(
            ["us-hot", "china-hot"],
            source="auto",
            limit=5,
            timeout=1.0,
            semantic_enabled=True,
            semantic_filter=True,
        )

        self.assertEqual(labeler.calls, [2])
        self.assertEqual([section.key for section in sections], ["us-hot", "china-hot"])
        self.assertEqual(len(sections[0].items), 1)
        self.assertEqual(len(sections[1].items), 0)
        self.assertEqual(sections[1].filtered_count, 1)


if __name__ == "__main__":
    unittest.main()
