from __future__ import annotations

import unittest
from unittest.mock import patch

from daily_cli.models import NewsItem, SectionResult
from daily_cli.semantic import TfidfLabeler
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
            filter_mode="model",
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
            filter_mode="model",
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

    @patch("daily_cli.service.fetch_google_news_search")
    @patch("daily_cli.service.get_semantic_labeler")
    def test_ai_preset_does_not_filter_by_default(
        self,
        mocked_labeler,
        mocked_google_news,
    ) -> None:
        labeler = StubLabeler()
        mocked_labeler.return_value = labeler
        mocked_google_news.return_value = [
            NewsItem(title="男子买车一年蹭饭260次还打包", category="ai", provider="google", feed="Google News")
        ]

        section = collect_presets(
            ["ai"],
            source="google",
            limit=5,
            timeout=1.0,
            semantic_enabled=True,
            semantic_filter=True,
        )[0]

        self.assertEqual(labeler.calls, [1])
        self.assertTrue(section.semantic_enabled)
        self.assertFalse(section.filter_enabled)
        self.assertEqual(section.filtered_count, 0)
        self.assertEqual(len(section.items), 1)


class TfidfLabelerTests(unittest.TestCase):
    def test_tfidf_labeler_marks_low_signal_story_as_soft(self) -> None:
        labeler = TfidfLabeler()
        items = [
            NewsItem(
                title="男子4S店买车一年蹭饭260次还打包",
                summary="店家无奈将其拉黑，男子称要维权，事件引发围观。",
                category="china-hot",
                provider="baidu",
                feed="Baidu Hotboard",
            )
        ]

        labeler.annotate_items(items)

        self.assertEqual(items[0].content_label, "soft")
        self.assertGreater(items[0].content_label_score, 0.0)

    def test_tfidf_labeler_marks_policy_story_as_macro(self) -> None:
        labeler = TfidfLabeler()
        items = [
            NewsItem(
                title="美联储暗示年内或继续降息",
                summary="市场重新评估利率路径与通胀走势。",
                category="finance",
                provider="google",
                feed="Google News",
            )
        ]

        labeler.annotate_items(items)

        self.assertEqual(items[0].content_label, "macro")

    def test_tfidf_labeler_marks_english_court_story_as_public(self) -> None:
        labeler = TfidfLabeler()
        items = [
            NewsItem(
                title="Judge ejects federal prosecutor from courtroom after ethics hearing",
                summary="The court said the prosecutor violated disclosure rules during the trial.",
                category="us-hot",
                provider="google",
                feed="Google Trends",
            )
        ]

        labeler.annotate_items(items)

        self.assertEqual(items[0].content_label, "public")

    def test_tfidf_labeler_marks_outbreak_story_as_public(self) -> None:
        labeler = TfidfLabeler()
        items = [
            NewsItem(
                title="Meningitis outbreak expands as health officials open vaccine clinics",
                summary="Hospitals and schools in the region issued new public safety guidance.",
                category="us-hot",
                provider="google",
                feed="Google Trends",
            )
        ]

        labeler.annotate_items(items)

        self.assertEqual(items[0].content_label, "public")

    def test_tfidf_labeler_marks_tariff_story_as_macro(self) -> None:
        labeler = TfidfLabeler()
        items = [
            NewsItem(
                title="White House weighs new tariffs as Fed officials monitor inflation",
                summary="Investors are watching trade policy, interest rates and the broader economy.",
                category="us-hot",
                provider="google",
                feed="Google Trends",
            )
        ]

        labeler.annotate_items(items)

        self.assertEqual(items[0].content_label, "macro")

    def test_tfidf_labeler_marks_allies_story_as_macro(self) -> None:
        labeler = TfidfLabeler()
        items = [
            NewsItem(
                title="美国的四大盟友 看向中国",
                summary="民调显示，多国受访者认为国际关系重心正在变化，对美国依赖下降。",
                category="china-hot",
                provider="baidu",
                feed="Baidu Hotboard",
            )
        ]

        labeler.annotate_items(items)

        self.assertEqual(items[0].content_label, "macro")

    def test_tfidf_labeler_marks_queue_story_as_soft(self) -> None:
        labeler = TfidfLabeler()
        items = [
            NewsItem(
                title="前方等位3200桌 女子排队到崩溃",
                summary="网红餐厅排队取号引发围观和热议。",
                category="china-hot",
                provider="baidu",
                feed="Baidu Hotboard",
            )
        ]

        labeler.annotate_items(items)

        self.assertEqual(items[0].content_label, "soft")


if __name__ == "__main__":
    unittest.main()
