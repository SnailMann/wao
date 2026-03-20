from __future__ import annotations

import unittest

from wao.core.output import render_text
from wao.core.models import NewsItem, SectionResult


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
                    body_text="这里是一段正文内容，用于验证输出层会把抓取到的正文一起展示出来。",
                    body_url="https://example.com/article",
                )
            ],
        )

        rendered = render_text([section])

        self.assertIn("语义标签: 开启", rendered)
        self.assertIn("过滤标签 soft", rendered)
        self.assertIn("分类: 宏观与政策 0.84", rendered)
        self.assertIn("正文:", rendered)
        self.assertIn("正文链接: https://example.com/article", rendered)

    def test_render_text_keeps_full_summary(self) -> None:
        long_summary = (
            "This is a deliberately long summary used to verify that text rendering keeps the entire "
            "payload intact instead of truncating it with an ellipsis in the default terminal output."
        )
        section = SectionResult(
            key="search",
            label='自定义查询: "ai make game"',
            requested_source="x",
            resolved_sources=["x"],
            generated_at="2026-03-20 20:00:00 CST",
            items=[
                NewsItem(
                    title="A complete item title",
                    category="search",
                    provider="x",
                    feed="X Search",
                    summary=long_summary,
                )
            ],
        )

        rendered = render_text([section])

        self.assertIn(long_summary, rendered)


if __name__ == "__main__":
    unittest.main()
