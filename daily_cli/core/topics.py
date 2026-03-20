from __future__ import annotations

from dataclasses import dataclass

from ..runtime.semantic import DEFAULT_EXCLUDED_LABELS

AI_GOOGLE_QUERY = 'AI OR "artificial intelligence" OR OpenAI OR Anthropic OR Gemini OR Nvidia'
FINANCE_GOOGLE_QUERY = (
    '"stock market" OR Nasdaq OR "S&P 500" OR "Dow Jones" OR '
    '"Federal Reserve" OR earnings OR inflation'
)
US_MARKET_GOOGLE_QUERY = '"US stocks" OR "stock market" OR Nasdaq OR "S&P 500" OR "Dow Jones"'

AI_KEYWORDS = (
    "ai",
    "artificial intelligence",
    "openai",
    "anthropic",
    "gemini",
    "nvidia",
    "人工智能",
    "大模型",
    "机器人",
    "智能体",
)
FINANCE_KEYWORDS = (
    "stock",
    "market",
    "nasdaq",
    "dow",
    "s&p",
    "fed",
    "finance",
    "financial",
    "earnings",
    "inflation",
    "金融",
    "财经",
    "股市",
    "美股",
    "a股",
    "黄金",
    "油价",
    "银行",
    "基金",
    "人民币",
    "债",
)
US_MARKET_KEYWORDS = (
    "美股",
    "纳指",
    "道指",
    "标普",
    "nasdaq",
    "dow",
    "s&p",
    "股票",
    "股指",
)


@dataclass(frozen=True)
class SourcePlan:
    source: str
    mode: str
    query: str = ""
    locale: str = "us"
    keywords: tuple[str, ...] = ()
    endpoint: str = ""


@dataclass(frozen=True)
class TopicSpec:
    key: str
    label: str
    description: str
    source_plans: tuple[SourcePlan, ...]
    default_sources: tuple[str, ...]
    default_limit: int
    default_excluded_labels: tuple[str, ...]
    refill_plan: SourcePlan | None = None

    @property
    def supported_sources(self) -> tuple[str, ...]:
        return tuple(dict.fromkeys(plan.source for plan in self.source_plans))


DEFAULT_SUMMARY_TOPICS = ("us-hot", "china-hot", "ai", "finance", "github")


TOPIC_SPECS = {
    "us-hot": TopicSpec(
        key="us-hot",
        label="美国热门事件",
        description="默认使用 Google Trends RSS，适合追踪美国当天热门搜索与事件。",
        source_plans=(
            SourcePlan(source="google", mode="trends_us"),
        ),
        default_sources=("google",),
        default_limit=5,
        default_excluded_labels=DEFAULT_EXCLUDED_LABELS,
        refill_plan=SourcePlan(source="google", mode="news_top", locale="us"),
    ),
    "china-hot": TopicSpec(
        key="china-hot",
        label="中国热门事件",
        description="默认使用百度热榜结构化数据。",
        source_plans=(
            SourcePlan(source="baidu", mode="hotboard"),
        ),
        default_sources=("baidu",),
        default_limit=5,
        default_excluded_labels=DEFAULT_EXCLUDED_LABELS,
    ),
    "ai": TopicSpec(
        key="ai",
        label="AI 发展",
        description="聚合 Google News RSS 与百度热榜中的 AI 相关条目。",
        source_plans=(
            SourcePlan(source="google", mode="news_search", query=AI_GOOGLE_QUERY, locale="us"),
            SourcePlan(source="baidu", mode="keyword_hotboard", keywords=AI_KEYWORDS),
        ),
        default_sources=("google", "baidu"),
        default_limit=5,
        default_excluded_labels=(),
    ),
    "finance": TopicSpec(
        key="finance",
        label="金融热门事件",
        description="聚合 Google News RSS 与百度热榜中的金融类条目。",
        source_plans=(
            SourcePlan(source="google", mode="news_search", query=FINANCE_GOOGLE_QUERY, locale="us"),
            SourcePlan(source="baidu", mode="keyword_hotboard", keywords=FINANCE_KEYWORDS),
        ),
        default_sources=("google", "baidu"),
        default_limit=5,
        default_excluded_labels=(),
    ),
    "us-market": TopicSpec(
        key="us-market",
        label="美股焦点",
        description="聚合 Google News 与百度热榜中的美股相关热点。",
        source_plans=(
            SourcePlan(source="google", mode="news_search", query=US_MARKET_GOOGLE_QUERY, locale="us"),
            SourcePlan(source="baidu", mode="keyword_hotboard", keywords=US_MARKET_KEYWORDS),
        ),
        default_sources=("google", "baidu"),
        default_limit=5,
        default_excluded_labels=(),
    ),
    "github": TopicSpec(
        key="github",
        label="GitHub Trending",
        description="获取 GitHub Trending 项目的热门仓库信息。",
        source_plans=(
            SourcePlan(source="github", mode="trending"),
        ),
        default_sources=("github",),
        default_limit=10,
        default_excluded_labels=(),
    ),
    "x": TopicSpec(
        key="x",
        label="X 用户动态",
        description="通过 X 官方 API v2 获取指定用户最近公开发推内容；需要先配置 Bearer Token。",
        source_plans=(
            SourcePlan(source="x", mode="user_tweets"),
        ),
        default_sources=("x",),
        default_limit=10,
        default_excluded_labels=(),
    ),
}


def get_topic(key: str) -> TopicSpec:
    try:
        return TOPIC_SPECS[key]
    except KeyError as exc:
        raise ValueError(f"Unknown topic: {key}") from exc


def list_topics() -> list[TopicSpec]:
    return [TOPIC_SPECS[key] for key in TOPIC_SPECS]


def list_topic_keys() -> tuple[str, ...]:
    return tuple(TOPIC_SPECS)


def build_search_topic(query: str, locale: str) -> TopicSpec:
    return TopicSpec(
        key="search",
        label=f'自定义查询: "{query}"',
        description="按用户查询进行 Google News 检索。",
        source_plans=(
            SourcePlan(
                source="google",
                mode="news_search",
                query=query,
                locale=locale,
            ),
        ),
        default_sources=("google",),
        default_limit=5,
        default_excluded_labels=(),
    )


def build_x_topic(username: str) -> TopicSpec:
    normalized = username.strip().lstrip("@")
    if not normalized:
        raise ValueError("fetch x 需要通过 --x-user 指定用户名，例如 `daily fetch x --x-user elonmusk`")

    return TopicSpec(
        key="x",
        label=f"X 用户: @{normalized}",
        description=f"通过 X 官方 API 获取 @{normalized} 最近公开发推内容。",
        source_plans=(
            SourcePlan(
                source="x",
                mode="user_tweets",
                query=normalized,
            ),
        ),
        default_sources=("x",),
        default_limit=10,
        default_excluded_labels=(),
    )


def get_source_plan(spec: TopicSpec, source: str) -> SourcePlan:
    for plan in spec.source_plans:
        if plan.source == source:
            return plan
    raise ValueError(f"{spec.key} 仅支持这些来源: {', '.join(spec.supported_sources)}")


def resolve_sources(spec: TopicSpec, requested_source: str) -> tuple[str, ...]:
    if requested_source == "auto":
        return spec.default_sources
    if requested_source == "all":
        return spec.supported_sources
    if requested_source not in spec.supported_sources:
        supported = ", ".join(spec.supported_sources)
        raise ValueError(f"{spec.key} 仅支持这些来源: {supported}")
    return (requested_source,)
