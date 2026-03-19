from __future__ import annotations

import unittest

from daily_cli.runtime.sources import (
    filter_items_by_keywords,
    parse_baidu_realtime_html,
    parse_github_trending_html,
    parse_google_news_rss,
    parse_google_trends_rss,
)


GOOGLE_TRENDS_SAMPLE = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<rss xmlns:atom="http://www.w3.org/2005/Atom" xmlns:ht="https://trends.google.com/trending/rss" version="2.0">
  <channel>
    <item>
      <title>comcast xfinity internet</title>
      <ht:approx_traffic>100+</ht:approx_traffic>
      <link>https://trends.google.com/trending/rss?geo=US</link>
      <pubDate>Wed, 18 Mar 2026 01:30:00 -0700</pubDate>
      <ht:news_item>
        <ht:news_item_title>Xfinity and Comcast Business High-Speed Fiber Internet Now Available in Cheney, Washington</ht:news_item_title>
        <ht:news_item_url>https://example.com/google-trends-1</ht:news_item_url>
        <ht:news_item_source>Business Wire</ht:news_item_source>
      </ht:news_item>
    </item>
  </channel>
</rss>
"""

GOOGLE_NEWS_SAMPLE = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<rss version="2.0">
  <channel>
    <item>
      <title>AI policy group makes recommendations on implementing state's AI law - Colorado Public Radio</title>
      <link>https://news.google.com/rss/articles/123</link>
      <pubDate>Tue, 17 Mar 2026 23:57:24 GMT</pubDate>
      <description>&lt;a href="https://news.google.com/rss/articles/123"&gt;AI policy group makes recommendations&lt;/a&gt;&amp;nbsp;&amp;nbsp;&lt;font color="#6f6f6f"&gt;Colorado Public Radio&lt;/font&gt;</description>
    </item>
  </channel>
</rss>
"""

BAIDU_REALTIME_SAMPLE = """
<html>
  <body>
    <div id="sanRoot"><!--s-data:{"data":{"cards":[{"component":"hotList","content":[{"word":"人工智能加速融入千行百业","desc":"AI 正在走向产业落地。","hotScore":"123456","url":"https://www.baidu.com/s?wd=%E4%BA%BA%E5%B7%A5%E6%99%BA%E8%83%BD","isTop":true},{"word":"油价上涨 冲锋衣可能变更贵","desc":"国际油价上涨带来成本压力。","hotScore":"654321","url":"https://www.baidu.com/s?wd=%E6%B2%B9%E4%BB%B7"}]}]}}--></div>
  </body>
</html>
"""

GITHUB_TRENDING_SAMPLE = """
<html>
  <body>
    <article class="Box-row">
      <h2 class="h3 lh-condensed">
        <a href="/jarrodwatts/claude-hud">
          <span class="text-normal">jarrodwatts /</span>
          claude-hud
        </a>
      </h2>
      <p class="col-9 color-fg-muted my-1 tmp-pr-4">
        A Claude Code plugin that shows what's happening.
      </p>
      <div class="f6 color-fg-muted mt-2">
        <span class="tmp-mr-3 d-inline-block ml-0">
          <span itemprop="programmingLanguage">JavaScript</span>
        </span>
        <a href="/jarrodwatts/claude-hud/stargazers">6,220</a>
        <a href="/jarrodwatts/claude-hud/forks">272</a>
        <span class="d-inline-block float-sm-right">1,040 stars today</span>
      </div>
    </article>
  </body>
</html>
"""

class SourceParserTests(unittest.TestCase):
    def test_parse_google_trends_rss(self) -> None:
        items = parse_google_trends_rss(GOOGLE_TRENDS_SAMPLE, limit=3, category="us-hot")
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].title, "comcast xfinity internet")
        self.assertEqual(items[0].publisher, "Business Wire")
        self.assertEqual(items[0].approx_traffic, "100+")
        self.assertEqual(items[0].link, "https://example.com/google-trends-1")

    def test_parse_google_news_rss(self) -> None:
        items = parse_google_news_rss(GOOGLE_NEWS_SAMPLE, limit=3, category="ai")
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].title, "AI policy group makes recommendations on implementing state's AI law")
        self.assertEqual(items[0].publisher, "Colorado Public Radio")
        self.assertIn("AI policy group makes recommendations", items[0].summary)

    def test_parse_baidu_realtime_html(self) -> None:
        items = parse_baidu_realtime_html(BAIDU_REALTIME_SAMPLE, limit=5, category="china-hot")
        self.assertEqual(len(items), 2)
        self.assertEqual(items[0].title, "人工智能加速融入千行百业")
        self.assertEqual(items[0].hot_score, "123456")
        self.assertIn("置顶", items[0].tags)

    def test_filter_items_by_keywords(self) -> None:
        hot_items = parse_baidu_realtime_html(BAIDU_REALTIME_SAMPLE, limit=5, category="china-hot")
        items = filter_items_by_keywords(
            hot_items,
            keywords=("人工智能", "AI"),
            limit=5,
            category="ai",
        )
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].title, "人工智能加速融入千行百业")
        self.assertEqual(items[0].category, "ai")

    def test_parse_github_trending_html(self) -> None:
        items = parse_github_trending_html(GITHUB_TRENDING_SAMPLE, limit=5, category="github")
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].title, "jarrodwatts/claude-hud")
        self.assertEqual(items[0].language, "JavaScript")
        self.assertEqual(items[0].repo_stars, "6,220")
        self.assertEqual(items[0].repo_forks, "272")
        self.assertEqual(items[0].stars_today, "1,040")
        self.assertEqual(items[0].link, "https://github.com/jarrodwatts/claude-hud")


if __name__ == "__main__":
    unittest.main()
