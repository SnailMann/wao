from __future__ import annotations

import unittest

from daily_cli.models import NewsItem, SectionResult
from daily_cli.output import render_text


class OutputRenderingTests(unittest.TestCase):
    def test_render_text_shows_semantic_metadata(self) -> None:
        section = SectionResult(
            key="china-hot",
            label="中国热门事件",
            requested_source="baidu",
            resolved_sources=["baidu"],
            generated_at="2026-03-18 22:00:00 CST",
            semantic_enabled=True,
            semantic_model="intfloat/multilingual-e5-small",
            filter_enabled=True,
            excluded_labels=["soft"],
            filtered_count=2,
            items=[
                NewsItem(
                    title="美联储暗示年内或继续降息",
                    category="china-hot",
                    provider="baidu",
                    feed="Baidu Hotboard",
                    content_label="macro",
                    content_label_name="宏观与政策",
                    content_label_score=0.84,
                )
            ],
        )

        rendered = render_text([section])

        self.assertIn("语义标签: 开启", rendered)
        self.assertIn("过滤标签 soft", rendered)
        self.assertIn("分类: 宏观与政策 0.84", rendered)


if __name__ == "__main__":
    unittest.main()
