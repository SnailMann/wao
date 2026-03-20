from __future__ import annotations

import unittest
from unittest.mock import patch

from wao.service.collector import _finalize_topic_section, collect_topics
from wao.core.models import NewsItem, SectionResult
from wao.plugins.semantic import TfidfLabeler


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


class UsHotRefillLabeler:
    def __init__(self) -> None:
        self.calls: list[int] = []

    def annotate_items(self, items: list[NewsItem]) -> list[NewsItem]:
        self.calls.append(len(items))
        for item in items:
            lowered = item.title.casefold()
            if any(term in lowered for term in ("niall", "masters", "movie", "concert", "album")):
                item.content_label = "soft"
                item.content_label_name = "软信息"
                item.content_label_score = 0.83
            else:
                item.content_label = "public"
                item.content_label_name = "公共事务"
                item.content_label_score = 0.76
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
    def test_default_soft_filter_removes_low_signal_items(self) -> None:
        labeler = StubLabeler()
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
                "spec": type("Spec", (), {"refill_plan": None})(),
                "final_limit": 5,
                "blocked_labels": ("soft",),
                "filter_active": True,
            },
        )()

        labeler.annotate_items(section.items)
        result = _finalize_topic_section(
            prepared,
            section,
            timeout=1.0,
            semantic_model_dir=None,
            filter_mode="tfidf",
        )

        self.assertTrue(result.semantic_enabled)
        self.assertTrue(result.filter_enabled)
        self.assertEqual(result.excluded_labels, ["soft"])
        self.assertEqual(result.filtered_count, 1)
        self.assertEqual(len(result.items), 1)
        self.assertEqual(result.items[0].title, "美联储暗示年内或继续降息")
        self.assertEqual(result.items[0].content_label, "macro")

    def test_custom_excluded_labels_override_default_soft_filter(self) -> None:
        labeler = StubLabeler()
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
                "spec": type("Spec", (), {"refill_plan": None})(),
                "final_limit": 5,
                "blocked_labels": ("public",),
                "filter_active": True,
            },
        )()

        labeler.annotate_items(section.items)
        result = _finalize_topic_section(
            prepared,
            section,
            timeout=1.0,
            semantic_model_dir=None,
            filter_mode="tfidf",
        )

        self.assertEqual(result.excluded_labels, ["public"])
        self.assertEqual(result.filtered_count, 0)
        self.assertEqual(len(result.items), 2)
        self.assertEqual(result.items[0].content_label, "soft")

    @patch("wao.service.collector.fetch_source_plan")
    @patch("wao.service.collector.annotate_items")
    def test_collect_topics_uses_single_global_annotation_batch(
        self,
        mocked_annotate,
        mocked_fetch_source_plan,
    ) -> None:
        labeler = StubLabeler()
        mocked_annotate.side_effect = lambda items, **kwargs: labeler.annotate_items(items)

        def side_effect(plan, topic_key, limit, timeout):
            if topic_key == "us-hot" and plan.mode == "trends_us":
                return [
                    NewsItem(
                        title="Federal Reserve signals more cuts",
                        category="us-hot",
                        provider="google",
                        feed="Google Trends",
                    )
                ]
            if topic_key == "china-hot" and plan.mode == "hotboard":
                return [
                    NewsItem(
                        title="男子买车一年蹭饭260次还打包",
                        category="china-hot",
                        provider="baidu",
                        feed="Baidu Hotboard",
                    )
                ]
            if topic_key == "us-hot" and plan.mode == "news_top":
                return []
            raise AssertionError(f"unexpected fetch: {topic_key} {plan.source}:{plan.mode}")

        mocked_fetch_source_plan.side_effect = side_effect

        sections = collect_topics(
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

    @patch("wao.service.collector.fetch_source_plan")
    @patch("wao.service.collector.annotate_items")
    def test_ai_topic_does_not_trigger_semantic_by_default(
        self,
        mocked_annotate,
        mocked_fetch_source_plan,
    ) -> None:
        mocked_fetch_source_plan.return_value = [
            NewsItem(title="男子买车一年蹭饭260次还打包", category="ai", provider="google", feed="Google News")
        ]

        section = collect_topics(
            ["ai"],
            source="google",
            limit=5,
            timeout=1.0,
            semantic_enabled=True,
            semantic_filter=True,
        )[0]

        mocked_annotate.assert_not_called()
        self.assertFalse(section.semantic_enabled)
        self.assertFalse(section.filter_enabled)
        self.assertEqual(section.filtered_count, 0)
        self.assertEqual(len(section.items), 1)
        self.assertEqual(section.items[0].content_label, "")

    @patch("wao.service.collector.fetch_source_plan")
    @patch("wao.service.collector.annotate_items")
    def test_github_topic_does_not_trigger_semantic_by_default(
        self,
        mocked_annotate,
        mocked_fetch_source_plan,
    ) -> None:
        mocked_fetch_source_plan.return_value = [
            NewsItem(title="obra/superpowers", category="github", provider="github", feed="GitHub Trending")
        ]

        section = collect_topics(
            ["github"],
            source="github",
            limit=10,
            timeout=1.0,
            semantic_enabled=True,
            semantic_filter=True,
        )[0]

        mocked_annotate.assert_not_called()
        self.assertFalse(section.semantic_enabled)
        self.assertFalse(section.filter_enabled)
        self.assertEqual(len(section.items), 1)
        self.assertEqual(section.items[0].content_label, "")

    @patch("wao.service.collector.fetch_source_plan")
    @patch("wao.service.collector.annotate_items")
    def test_github_topic_triggers_semantic_when_excluded_labels_are_provided(
        self,
        mocked_annotate,
        mocked_fetch_source_plan,
    ) -> None:
        labeler = StubLabeler()
        mocked_annotate.side_effect = lambda items, **kwargs: labeler.annotate_items(items)
        mocked_fetch_source_plan.return_value = [
            NewsItem(title="男子买车一年蹭饭260次还打包", category="github", provider="github", feed="GitHub Trending")
        ]

        section = collect_topics(
            ["github"],
            source="github",
            limit=10,
            timeout=1.0,
            semantic_enabled=True,
            semantic_filter=True,
            excluded_labels=("soft",),
        )[0]

        self.assertEqual(labeler.calls, [1])
        self.assertTrue(section.semantic_enabled)
        self.assertTrue(section.filter_enabled)
        self.assertEqual(section.filtered_count, 1)

    @patch("wao.service.collector.fetch_source_plan")
    @patch("wao.service.collector.annotate_items")
    def test_us_hot_refills_with_google_news_after_soft_filter(
        self,
        mocked_annotate,
        mocked_fetch_source_plan,
    ) -> None:
        labeler = UsHotRefillLabeler()
        mocked_annotate.side_effect = lambda items, **kwargs: labeler.annotate_items(items)

        def side_effect(plan, topic_key, limit, timeout):
            if topic_key == "us-hot" and plan.mode == "trends_us":
                return [
                    NewsItem(title="niall horan", category="us-hot", provider="google", feed="Google Trends"),
                    NewsItem(title="masters 2026", category="us-hot", provider="google", feed="Google Trends"),
                ]
            if topic_key == "us-hot" and plan.mode == "news_top":
                return [
                    NewsItem(
                        title="denver airport",
                        summary="Power outage impacts train service to gates.",
                        publisher="CBS News",
                        category="us-hot",
                        provider="google",
                        feed="Google News",
                    ),
                    NewsItem(
                        title="meningococcal meningitis outbreak",
                        summary="Health officials raise alarms after outbreak expands.",
                        publisher="The New York Times",
                        category="us-hot",
                        provider="google",
                        feed="Google News",
                    ),
                ]
            raise AssertionError(f"unexpected fetch: {topic_key} {plan.source}:{plan.mode}")

        mocked_fetch_source_plan.side_effect = side_effect

        section = collect_topics(
            ["us-hot"],
            source="google",
            limit=2,
            timeout=1.0,
            semantic_enabled=True,
            semantic_filter=True,
        )[0]

        self.assertEqual(labeler.calls, [2, 2])
        self.assertEqual([item.title for item in section.items], ["denver airport", "meningococcal meningitis outbreak"])
        self.assertEqual(section.filtered_count, 2)
        self.assertEqual(mocked_fetch_source_plan.call_count, 2)

    @patch("wao.fetchers.body.fetch_item_bodies")
    @patch("wao.service.collector.fetch_source_plan")
    @patch("wao.service.collector.annotate_items")
    def test_body_fetch_only_runs_on_final_kept_items(
        self,
        mocked_annotate,
        mocked_fetch_source_plan,
        mocked_fetch_bodies,
    ) -> None:
        labeler = UsHotRefillLabeler()
        mocked_annotate.side_effect = lambda items, **kwargs: labeler.annotate_items(items)
        mocked_fetch_source_plan.return_value = [
            NewsItem(
                title="niall horan",
                category="us-hot",
                provider="google",
                feed="Google Trends",
                link="https://example.com/niall",
            ),
            NewsItem(
                title="denver airport",
                summary="Power outage impacts train service to gates.",
                category="us-hot",
                provider="google",
                feed="Google Trends",
                link="https://example.com/airport",
            ),
        ]

        section = collect_topics(
            ["us-hot"],
            source="google",
            limit=1,
            timeout=1.0,
            semantic_enabled=True,
            semantic_filter=True,
            fetch_body=True,
            body_timeout=3.0,
            body_max_chars=1000,
        )[0]

        self.assertEqual([item.title for item in section.items], ["denver airport"])
        mocked_fetch_bodies.assert_called_once()
        body_items = mocked_fetch_bodies.call_args.args[0]
        self.assertEqual([item.title for item in body_items], ["denver airport"])
        self.assertEqual(mocked_fetch_bodies.call_args.kwargs["timeout"], 3.0)
        self.assertEqual(mocked_fetch_bodies.call_args.kwargs["max_chars"], 1000)

    @patch("wao.service.collector.fetch_source_plan")
    @patch("wao.service.collector.annotate_items")
    def test_us_hot_skips_google_news_refill_when_enough_items_remain(
        self,
        mocked_annotate,
        mocked_fetch_source_plan,
    ) -> None:
        labeler = UsHotRefillLabeler()
        mocked_annotate.side_effect = lambda items, **kwargs: labeler.annotate_items(items)
        mocked_fetch_source_plan.return_value = [
            NewsItem(
                title="denver airport",
                summary="Power outage impacts train service to gates.",
                category="us-hot",
                provider="google",
                feed="Google Trends",
            ),
            NewsItem(
                title="meningococcal meningitis outbreak",
                summary="Health officials raise alarms after outbreak expands.",
                category="us-hot",
                provider="google",
                feed="Google Trends",
            ),
        ]

        section = collect_topics(
            ["us-hot"],
            source="google",
            limit=2,
            timeout=1.0,
            semantic_enabled=True,
            semantic_filter=True,
        )[0]

        self.assertEqual(labeler.calls, [2])
        self.assertEqual(len(section.items), 2)
        self.assertEqual(mocked_fetch_source_plan.call_count, 1)


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

    def test_tfidf_labeler_marks_entertainment_story_as_soft(self) -> None:
        labeler = TfidfLabeler()
        items = [
            NewsItem(
                title="movies coming out in 2026",
                summary="Best new streaming movies and entertainment picks for the year.",
                category="us-hot",
                provider="google",
                feed="Google Trends",
            )
        ]

        labeler.annotate_items(items)

        self.assertEqual(items[0].content_label, "soft")

    def test_tfidf_labeler_marks_family_rescue_story_as_soft(self) -> None:
        labeler = TfidfLabeler()
        items = [
            NewsItem(
                title="“我想跳下去 但想到了老婆孩子”",
                summary=(
                    "市民在珠江边垂钓时发现有人落水，起初想下水施救，"
                    "但因挂念妻儿而放弃贸然下水，随后持续呼喊求救并引来水警。"
                ),
                category="china-hot",
                provider="baidu",
                feed="Baidu Hotboard",
            )
        ]

        labeler.annotate_items(items)

        self.assertEqual(items[0].content_label, "soft")

    def test_tfidf_labeler_marks_background_check_story_as_soft(self) -> None:
        labeler = TfidfLabeler()
        items = [
            NewsItem(
                title="前同事背调一句话 男子月薪少5千",
                summary=(
                    "北京丰台法院审理一起背景调查不实导致求职者降薪的案件，"
                    "背调公司因前同事关于生活作风问题的一句话出具报告。"
                ),
                category="china-hot",
                provider="baidu",
                feed="Baidu Hotboard",
            )
        ]

        labeler.annotate_items(items)

        self.assertEqual(items[0].content_label, "soft")

    def test_tfidf_labeler_marks_fake_office_story_as_soft(self) -> None:
        labeler = TfidfLabeler()
        items = [
            NewsItem(
                title="假装上班公司有“员工”月入七八万",
                summary=(
                    "杭州一家提供付费工位的假装上班公司走红，"
                    "每天花30元就能体验朝九晚五和加班到深夜。"
                ),
                category="china-hot",
                provider="baidu",
                feed="Baidu Hotboard",
            )
        ]

        labeler.annotate_items(items)

        self.assertEqual(items[0].content_label, "soft")

    def test_tfidf_labeler_marks_album_announcement_as_soft(self) -> None:
        labeler = TfidfLabeler()
        items = [
            NewsItem(
                title="niall horan",
                summary="Niall Horan announces a new album, release date and summer tour plans.",
                category="us-hot",
                provider="google",
                feed="Google Trends",
                publisher="Clash Magazine",
            )
        ]

        labeler.annotate_items(items)

        self.assertEqual(items[0].content_label, "soft")

    def test_tfidf_labeler_marks_middle_east_conflict_story_as_macro(self) -> None:
        labeler = TfidfLabeler()
        items = [
            NewsItem(
                title="以防长称伊朗情报部长身亡",
                summary="消息称中东冲突升级，伊朗情报系统高层在袭击中死亡。",
                category="china-hot",
                provider="baidu",
                feed="Baidu Hotboard",
            )
        ]

        labeler.annotate_items(items)

        self.assertEqual(items[0].content_label, "macro")


if __name__ == "__main__":
    unittest.main()
