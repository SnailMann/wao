from __future__ import annotations

import contextlib
from collections import Counter
from dataclasses import dataclass
from functools import lru_cache
import io
import math
import os
from pathlib import Path
import re
import shutil
import subprocess
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

MODEL_REPO_ID = "intfloat/multilingual-e5-small"
MODEL_CACHE_DIRNAME = "intfloat__multilingual-e5-small"
TFIDF_BACKEND_ID = "tfidf-lexicon"
APP_CACHE_DIRNAME = "wao"
LEGACY_APP_CACHE_DIRNAMES = ("daily", "daily-cli")
REQUIRED_MODEL_FILES = (
    "config.json",
    "model.safetensors",
    "tokenizer.json",
    "tokenizer_config.json",
    "special_tokens_map.json",
    "sentencepiece.bpe.model",
)


class SemanticError(RuntimeError):
    """Raised when semantic labeling is unavailable or misconfigured."""


@dataclass(frozen=True)
class ContentLabelSpec:
    key: str
    label: str
    prototype: str


LABEL_SPECS = (
    ContentLabelSpec(
        key="macro",
        label="宏观",
        prototype=(
            "宏观经济、政策监管、央行利率、财政、通胀、国际关系、贸易、制裁、选举、"
            "地缘政治。 macro economy, policy, regulation, central bank, rates, "
            "inflation, trade, sanctions, election, geopolitics."
        ),
    ),
    ContentLabelSpec(
        key="industry",
        label="商业",
        prototype=(
            "公司经营、财报、融资、并购、产业链、供应链、市场竞争、商业扩张、品牌与产品。 "
            "business, company, earnings, funding, mergers, supply chain, industry, competition."
        ),
    ),
    ContentLabelSpec(
        key="tech",
        label="科技",
        prototype=(
            "人工智能、大模型、芯片、软件、开源、研发、机器人、科学技术突破。 "
            "AI, large language model, chips, software, open source, research, robotics, technology."
        ),
    ),
    ContentLabelSpec(
        key="public",
        label="公共事务",
        prototype=(
            "公共事务、社会治理、法律案件、灾害事故、医疗教育、基础设施、公共安全、民生议题。 "
            "public affairs, law, safety, disaster, health, education, infrastructure."
        ),
    ),
    ContentLabelSpec(
        key="soft",
        label="软信息",
        prototype=(
            "猎奇八卦、情绪化社会新闻、个体纠纷、婚恋家事、明星绯闻、流量话题、"
            "没有明显公共价值或认知增量的软新闻。 gossip, bizarre quarrel, celebrity, "
            "entertainment, soft news, clickbait, low-information story."
        ),
    ),
)

LABEL_SPEC_BY_KEY = {spec.key: spec for spec in LABEL_SPECS}
DEFAULT_EXCLUDED_LABELS = ("soft",)
FILTER_BACKENDS = ("model", "tfidf")
ASCII_TOKEN_RE = re.compile(r"[a-z0-9][a-z0-9'+.#/_-]*")
CJK_SPAN_RE = re.compile(r"[\u4e00-\u9fff]+")
ASCII_KEEP_SHORT = frozenset({"ai", "uk", "us", "eu", "un", "fed", "ev", "vr", "ar"})
ASCII_STEM_EXCEPTIONS = frozenset(
    {
        "ai",
        "analysis",
        "anthropic",
        "campus",
        "chip",
        "chips",
        "congress",
        "crisis",
        "deepseek",
        "earnings",
        "economics",
        "federal",
        "geopolitics",
        "github",
        "gossip",
        "health",
        "headquarters",
        "inflation",
        "justice",
        "meningitis",
        "news",
        "openai",
        "politics",
        "robotics",
        "series",
        "software",
        "supplies",
        "tesla",
        "virus",
    }
)
EN_STOPWORDS = frozenset(
    {
        "a",
        "an",
        "and",
        "are",
        "as",
        "at",
        "be",
        "by",
        "for",
        "from",
        "how",
        "in",
        "into",
        "is",
        "it",
        "of",
        "on",
        "or",
        "that",
        "the",
        "their",
        "this",
        "to",
        "was",
        "were",
        "will",
        "with",
    }
)

LABEL_KEYWORDS: dict[str, tuple[str, ...]] = {
    "macro": (
        "宏观",
        "政策",
        "监管",
        "央行",
        "利率",
        "财政",
        "通胀",
        "经济",
        "发改委",
        "国务院",
        "财政部",
        "商务部",
        "外交部",
        "关税",
        "贸易战",
        "降息",
        "加息",
        "就业",
        "汇率",
        "人民币",
        "盟友",
        "国际关系",
        "外交关系",
        "民调",
        "制裁",
        "选举",
        "外交",
        "战争",
        "贸易",
        "原油",
        "白宫",
        "政府",
        "议会",
        "国会",
        "参议院",
        "众议院",
        "白宫",
        "美联储",
        "国债",
        "预算",
        "ceasefire",
        "central bank",
        "congress",
        "economic policy",
        "employment",
        "fed",
        "federal reserve",
        "foreign ministry",
        "foreign policy",
        "gdp",
        "government",
        "house",
        "oil",
        "inflation",
        "interest rate",
        "jobs report",
        "ministry",
        "powell",
        "rates",
        "sanction",
        "senate",
        "tariff",
        "treasury",
        "unemployment",
        "white house",
        "allies",
        "ally",
        "diplomatic",
        "geopolitics",
        "中东",
        "防长",
        "情报部长",
        "革命卫队",
        "无人机袭击",
        "天然气供应",
        "能源安全",
        "gas supply",
        "energy security",
        "intelligence minister",
        "defense minister",
        "military strike",
    ),
    "industry": (
        "公司",
        "产业",
        "供应链",
        "财报",
        "并购",
        "融资",
        "投资",
        "制造业",
        "企业",
        "门店",
        "销量",
        "销售",
        "品牌",
        "扩产",
        "出货",
        "收购",
        "合作",
        "订单",
        "盈利",
        "亏损",
        "零售",
        "汽车",
        "新能源车",
        "acquisition",
        "airline",
        "automaker",
        "brand",
        "business",
        "company",
        "consumer",
        "earnings",
        "factory",
        "funding",
        "merger",
        "industry",
        "investment",
        "manufacturing",
        "partnership",
        "plant",
        "profit",
        "revenue",
        "retail",
        "sales",
        "startup",
        "supply chain",
        "supplier",
    ),
    "tech": (
        "人工智能",
        "大模型",
        "芯片",
        "算力",
        "开源",
        "软件",
        "机器人",
        "科技",
        "智能体",
        "半导体",
        "推理",
        "算法",
        "模型",
        "研发",
        "数据库",
        "云计算",
        "ai",
        "agent",
        "openai",
        "anthropic",
        "deepseek",
        "gemini",
        "gpt",
        "llm",
        "semiconductor",
        "nvidia",
        "model",
        "chip",
        "cloud",
        "cuda",
        "data center",
        "developer",
        "inference",
        "machine learning",
        "research",
        "robotics",
        "software",
        "open source",
        "robot",
    ),
    "public": (
        "公共",
        "民生",
        "安全",
        "法律",
        "司法",
        "教育",
        "医疗",
        "灾害",
        "事故",
        "基础设施",
        "法院",
        "检察院",
        "公安",
        "警方",
        "医院",
        "学校",
        "疫情",
        "疾病",
        "疫苗",
        "暴雨",
        "洪水",
        "地震",
        "台风",
        "火灾",
        "爆炸",
        "机场",
        "航班",
        "延误",
        "取消",
        "交通事故",
        "airport",
        "courtroom",
        "court",
        "crime",
        "delay",
        "disaster",
        "education",
        "emergency",
        "epidemic",
        "evacuation",
        "flight",
        "fire",
        "flood",
        "health",
        "hospital",
        "judge",
        "judicial",
        "justice department",
        "law",
        "lawsuit",
        "meningitis",
        "outbreak",
        "police",
        "prosecutor",
        "public safety",
        "school",
        "shooting",
        "storm",
        "trial",
        "vaccine",
        "wildfire",
        "health",
        "infrastructure",
        "cancel",
        "safety",
    ),
    "soft": (
        "八卦",
        "猎奇",
        "奇葩",
        "情感",
        "婚恋",
        "家事",
        "绯闻",
        "网红",
        "围观",
        "蹭饭",
        "打包",
        "出殡",
        "离奇",
        "相亲",
        "恋爱",
        "明星",
        "爆料",
        "热梗",
        "戏精",
        "崩溃",
        "打卡",
        "排队",
        "等位",
        "网红餐厅",
        "爆火",
        "围观热议",
        "老婆孩子",
        "妻儿",
        "背调",
        "前同事",
        "一句话",
        "月薪",
        "降薪",
        "生活作风",
        "跳下去",
        "落水",
        "垂钓",
        "挂念",
        "假装上班",
        "付费工位",
        "朝九晚五",
        "加班费",
        "月入七八万",
        "高学历标签",
        "送外卖",
        "看女儿",
        "看望",
        "刷屏",
        "欢呼鼓掌",
        "汉服",
        "御剑飞行",
        "演唱会",
        "综艺",
        "电影",
        "追星",
        "直播",
        "专辑",
        "新专辑",
        "单曲",
        "歌手",
        "艺人",
        "乐队",
        "巡演",
        "票房",
        "票务",
        "boyfriend",
        "concert",
        "entertainment",
        "album",
        "artist",
        "band",
        "football",
        "golf",
        "match",
        "movie",
        "movies",
        "music",
        "nba",
        "nfl",
        "player",
        "release date",
        "single",
        "singer",
        "showbiz",
        "soccer",
        "sports",
        "streaming",
        "ticket",
        "tour",
        "celebrity",
        "clickbait",
        "dating",
        "divorce",
        "drama",
        "family feud",
        "girlfriend",
        "gossip",
        "bizarre",
        "quarrel",
        "romance",
        "scandal",
        "soft news",
        "viral",
        "wedding",
        "weird",
    ),
}

# Small bilingual seed corpora used to stabilize the lexical backend
# around the same label boundaries as the embedding model.
LABEL_TRAINING_SAMPLES: dict[str, tuple[str, ...]] = {
    "macro": (
        "美联储暗示年内或继续降息，市场重新评估利率路径和通胀走势。",
        "美国的四大盟友看向中国，民调显示国际关系重心正在变化。",
        "国务院部署新一轮宏观政策，强调财政与就业协同发力。",
        "White House weighs new tariffs as Fed officials monitor inflation.",
        "Central bank signals possible rate cuts amid rising unemployment.",
        "Diplomatic tensions escalate as allies debate foreign policy options.",
        "今夜美联储料按兵不动，鲍威尔需要在通胀和增长之间寻找平衡。",
        "外交部表示中美双方将继续就总统访华事保持沟通。",
        "爱尔兰总理当特朗普面批关税和战争，欧美关系再起波澜。",
        "New economic projections signal a tricky Federal Reserve path.",
        "伊朗表示将打击中东三国石油设施，地区地缘风险快速升高。",
        "伊拉克称伊朗天然气供应完全中断，中东能源安全风险再度升高。",
        "以防长称伊朗情报部长身亡，中东冲突与情报战进一步升级。",
    ),
    "industry": (
        "发改委推出新一批重大外资项目，制造业和汽车产业链继续扩张。",
        "公司发布财报后扩大门店与供应链投资。",
        "新能源车厂商提升销量并推进上游供应链合作。",
        "Startup raises funding as automaker expands factory capacity.",
        "Company posts strong earnings, revenue growth and new retail plans.",
        "Manufacturing investment grows as suppliers add new orders.",
        "畅通科创企业融资渠道，提升创新企业资本可得性。",
        "奇瑞汽车营收首破3000亿元，过半收入来自海外市场。",
        "微博发布财报，净利润同比增长49%。",
        "零跑汽车首度实现全年盈利，成为新能源车行业黑马。",
        "腾讯Q4营收同比增长13%，云业务全年实现规模化盈利。",
        "SEC moves closer to ending quarterly earnings requirement.",
        "Covetrus and MWI announce a multibillion-dollar merger.",
    ),
    "tech": (
        "OpenAI launches a new model for agentic coding and developer workflows.",
        "Nvidia unveils a new AI chip and data center software stack.",
        "人工智能大模型推理芯片和开源软件平台迎来升级。",
        "机器人研发团队发布新的智能体系统和算法能力。",
        "Machine learning researchers release an open source inference toolkit.",
        "Semiconductor company ships a new cloud AI accelerator.",
        "阿里百度AI算力产品涨价，核心原因来自芯片供给变化。",
        "科技向善，不能让AI技术沦为违法帮凶。",
        "北京海淀举办人工智能发展趋势国际交流会。",
        "Nvidia prepares for a return to China's AI chip market.",
        "价值3000亿美元的印度外包产业正在接受AI浪潮冲击。",
        "人工智能加速激活制造业新动能。",
    ),
    "public": (
        "Judge ejects federal prosecutor from courtroom after ethics hearing.",
        "Meningitis outbreak expands as health officials open vaccine clinics.",
        "Hundreds of flights delayed after storms at a major airport.",
        "医院发布疫苗接种和公共安全提示，学校同步调整安排。",
        "洪水和地震导致多地紧急疏散与基础设施受损。",
        "Police and emergency teams respond after a public safety incident.",
        "多地中考新方案公布，教育治理改革持续推进。",
        "Several court-related bills pass as session ends without budget deal.",
        "Court to hear argument in case that could have significant impact on elections.",
        "政绩观决定司法理念，法院系统强调依法履职。",
        "法院发布新一批司法公告和审判安排。",
    ),
    "soft": (
        "男子4S店买车一年蹭饭260次还打包，事件引发围观。",
        "前方等位3200桌，女子排队到崩溃，网红餐厅冲上热搜。",
        "网红爆料情感纠纷，围观热议不断发酵。",
        "“我想跳下去 但想到了老婆孩子”，个体情绪化叙事和家庭牵挂引发围观。",
        "前同事背调一句话让男子月薪少了五千，围绕生活作风和降薪的个案传播。",
        "点外卖米饭变质后商家只赔米饭钱，案件细节比公共价值更吸引围观。",
        "九旬夫妻两天内相继去世共同出殡，这类情绪化个体故事容易成为低信息热搜。",
        "Concert tour announcement and celebrity fan frenzy dominate social media.",
        "Streaming movie rankings and entertainment gossip take over trending searches.",
        "Football and golf prediction chatter turns into another sports clickbait cycle.",
        "Celebrity wedding gossip goes viral on social media.",
        "Boyfriend girlfriend drama sparks online feud and clickbait headlines.",
        "Bizarre family feud turns into another low-information viral story.",
        "前同事背调一句话让男子月薪少了五千，引发网友围观。",
        "假装上班公司提供付费工位和朝九晚五体验，月入七八万的故事冲上热搜。",
        "高学历标签和送外卖视频引发流量讨论，围绕个体人设的争议刷屏。",
        "审批通过后大批明星马上来武汉，演唱会经济成为热搜话题。",
        "男子坐30小时大巴扛200斤特产看女儿，情绪化故事刷屏。",
        "网红转型明星后持续爆红，围绕流量和人设的讨论发酵。",
        "新春市集与明星演唱会联动，票根经济引发大规模围观。",
        "歌手官宣新专辑和巡演计划，粉丝围绕发行日期和票务信息热议。",
        "Artist announces a new album, release date and summer tour stop.",
        "Singer reveals a single, track list and ticket plan for the upcoming tour.",
        "Bears sign a defensive tackle to a one-year deal as transfer chatter heats up.",
        "Masters picks and tournament betting stories dominate Augusta search trends.",
        "A singer announces a summer concert stop and local entertainment news surges.",
        "Club comeback dreams and match previews flood soccer hot searches.",
    ),
}

SOFT_STORY_CUES = (
    "老婆孩子",
    "妻儿",
    "背调",
    "前同事",
    "一句话",
    "月薪",
    "降薪",
    "生活作风",
    "跳下去",
    "落水",
    "垂钓",
    "挂念",
    "围观",
    "崩溃",
    "蹭饭",
    "打包",
    "出殡",
    "假装上班",
    "付费工位",
    "朝九晚五",
    "加班费",
    "月入七八万",
    "高学历标签",
    "送外卖",
    "看女儿",
    "看望",
    "刷屏",
    "欢呼鼓掌",
    "汉服",
    "御剑飞行",
    "album",
    "single",
    "singer",
    "tour",
    "release date",
)


def list_content_labels() -> tuple[str, ...]:
    return tuple(spec.key for spec in LABEL_SPECS)


def list_filter_backends() -> tuple[str, ...]:
    return FILTER_BACKENDS


def get_content_label_name(key: str) -> str:
    spec = LABEL_SPEC_BY_KEY.get(key)
    return spec.label if spec is not None else key


def default_model_dir() -> Path:
    return Path.home() / ".cache" / APP_CACHE_DIRNAME / "models" / MODEL_CACHE_DIRNAME


def legacy_model_dirs() -> tuple[Path, ...]:
    return tuple(
        Path.home() / ".cache" / dirname / "models" / MODEL_CACHE_DIRNAME
        for dirname in LEGACY_APP_CACHE_DIRNAMES
    )


def resolve_default_model_dir(model_dir: str | None = None) -> Path:
    if model_dir:
        return Path(model_dir).expanduser()

    preferred = default_model_dir()
    if preferred.exists():
        return preferred

    for legacy in legacy_model_dirs():
        if legacy.exists():
            return legacy

    return preferred


def _resolve_hf_token() -> str:
    for name in ("HF_TOKEN", "HUGGINGFACE_HUB_TOKEN"):
        value = os.environ.get(name, "").strip()
        if value:
            return value

    token_file = Path.home() / ".cache" / "huggingface" / "token"
    if token_file.exists():
        value = token_file.read_text(encoding="utf-8").strip()
        if value:
            return value

    return ""


def _load_runtime_dependencies():
    try:
        import torch
        import torch.nn.functional as functional
        from transformers import AutoModel, AutoTokenizer, logging as transformers_logging
    except ImportError as exc:
        raise SemanticError(
            "model 过滤依赖未安装，请先执行 `python3 -m pip install .[model]`。"
        ) from exc
    transformers_logging.set_verbosity_error()
    return torch, functional, AutoModel, AutoTokenizer


def _load_sklearn_dependencies():
    try:
        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.linear_model import LogisticRegression
    except ImportError as exc:
        raise SemanticError(
            "TF-IDF 过滤依赖未安装，请先执行 `python3 -m pip install .`。"
        ) from exc
    return TfidfVectorizer, LogisticRegression


def _download_file(file_name: str, destination: Path) -> None:
    url = f"https://huggingface.co/{MODEL_REPO_ID}/resolve/main/{file_name}"
    temp_path = destination.with_suffix(destination.suffix + ".part")
    curl_path = shutil.which("curl")
    token = _resolve_hf_token()

    if curl_path and not token:
        command = [
            curl_path,
            "-fL",
            "--retry",
            "3",
            "--connect-timeout",
            "30",
            "-o",
            str(temp_path),
            url,
        ]
        if temp_path.exists():
            command[1:1] = ["-C", "-"]
        try:
            subprocess.run(command, check=True)
            temp_path.replace(destination)
            return
        except subprocess.CalledProcessError as exc:
            raise SemanticError(f"下载模型文件失败: {file_name} curl 退出码 {exc.returncode}") from exc

    headers = {"User-Agent": "wao/0.2"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = Request(url, headers=headers)

    try:
        with urlopen(request, timeout=120) as response, temp_path.open("wb") as handle:
            while True:
                chunk = response.read(1024 * 1024)
                if not chunk:
                    break
                handle.write(chunk)
    except HTTPError as exc:
        raise SemanticError(f"下载模型文件失败: {file_name} 返回 HTTP {exc.code}") from exc
    except URLError as exc:
        raise SemanticError(f"下载模型文件失败: {file_name} 网络不可用: {exc.reason}") from exc

    temp_path.replace(destination)


def ensure_model_downloaded(model_dir: str | None = None) -> str:
    target_dir = resolve_default_model_dir(model_dir)
    missing = [name for name in REQUIRED_MODEL_FILES if not (target_dir / name).exists()]
    if missing:
        joined = ", ".join(missing)
        raise SemanticError(
            "语义模型尚未准备好，请先运行 `wao model download`。"
            f" 当前目录缺少: {joined}"
        )
    return str(target_dir)


def download_model(model_dir: str | None = None, force: bool = False) -> str:
    target_dir = resolve_default_model_dir(model_dir)
    target_dir.mkdir(parents=True, exist_ok=True)

    if force:
        for file_name in REQUIRED_MODEL_FILES:
            file_path = target_dir / file_name
            if file_path.exists():
                file_path.unlink()

    for file_name in REQUIRED_MODEL_FILES:
        destination = target_dir / file_name
        if destination.exists() and not force:
            continue
        _download_file(file_name, destination)

    return ensure_model_downloaded(str(target_dir))


class SemanticLabeler:
    def __init__(self, model_dir: str | None = None) -> None:
        resolved_model_dir = ensure_model_downloaded(model_dir)
        torch, functional, AutoModel, AutoTokenizer = _load_runtime_dependencies()

        self._torch = torch
        self._functional = functional
        self._tokenizer = AutoTokenizer.from_pretrained(resolved_model_dir, local_files_only=True)
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            self._model = AutoModel.from_pretrained(resolved_model_dir, local_files_only=True)
        self._model.eval()
        self._label_specs = LABEL_SPECS
        self._label_embeddings = self._encode(
            [spec.prototype for spec in self._label_specs],
            prefix="passage",
        )

    def _encode(self, texts: list[str], prefix: str) -> object:
        prepared = [f"{prefix}: {text}".strip() for text in texts]
        encoded = self._tokenizer(
            prepared,
            padding=True,
            truncation=True,
            max_length=256,
            return_tensors="pt",
        )
        with self._torch.no_grad():
            outputs = self._model(**encoded)

        token_embeddings = outputs.last_hidden_state
        attention_mask = encoded["attention_mask"].unsqueeze(-1).expand(token_embeddings.size()).float()
        summed = (token_embeddings * attention_mask).sum(dim=1)
        counts = attention_mask.sum(dim=1).clamp(min=1e-9)
        embeddings = summed / counts
        return self._functional.normalize(embeddings, p=2, dim=1)

    def annotate_items(self, items: list[object], batch_size: int = 32) -> list[object]:
        if not items:
            return items

        for start in range(0, len(items), batch_size):
            batch_items = items[start : start + batch_size]
            texts: list[str] = []
            for item in batch_items:
                parts = [getattr(item, "title", ""), getattr(item, "summary", ""), getattr(item, "publisher", "")]
                text = "\n".join(part.strip() for part in parts if part and part.strip())
                texts.append(text or getattr(item, "title", ""))

            query_embeddings = self._encode(texts, prefix="query")
            scores = query_embeddings @ self._label_embeddings.T

            for index, item in enumerate(batch_items):
                row = scores[index]
                best_index = int(row.argmax().item())
                best_score = float(row[best_index].item())
                spec = self._label_specs[best_index]
                item.content_label = spec.key
                item.content_label_name = spec.label
                item.content_label_score = best_score

        return items


def _tokenize_text(text: str) -> list[str]:
    tokens: list[str] = []
    tokens.extend(_tokenize_ascii_text(text))
    tokens.extend(_tokenize_cjk_text(text))
    return tokens


def _normalize_ascii_token(token: str) -> str:
    normalized = token.casefold().strip("._-/+#")
    if normalized.endswith("'s"):
        normalized = normalized[:-2]
    if not normalized:
        return ""
    if normalized in EN_STOPWORDS:
        return ""
    if normalized.isdigit():
        return normalized
    if normalized not in ASCII_STEM_EXCEPTIONS:
        if normalized.endswith("ies") and len(normalized) > 5:
            normalized = normalized[:-3] + "y"
        elif normalized.endswith("ing") and len(normalized) > 6:
            normalized = normalized[:-3]
        elif normalized.endswith("ed") and len(normalized) > 5:
            normalized = normalized[:-2]
        elif normalized.endswith("es") and len(normalized) > 5 and not normalized.endswith(("ses", "xes", "zes", "ches", "shes")):
            normalized = normalized[:-2]
        elif normalized.endswith("s") and len(normalized) > 4 and not normalized.endswith(("ss", "is", "us")):
            normalized = normalized[:-1]
    if normalized in EN_STOPWORDS:
        return ""
    if len(normalized) <= 2 and normalized not in ASCII_KEEP_SHORT:
        return ""
    return normalized


def _tokenize_ascii_text(text: str) -> list[str]:
    tokens: list[str] = []
    for raw in ASCII_TOKEN_RE.findall((text or "").casefold()):
        parts = re.split(r"[+#./_-]+", raw)
        for part in parts:
            normalized = _normalize_ascii_token(part)
            if normalized:
                tokens.append(normalized)
    return tokens


def _tokenize_cjk_text(text: str) -> list[str]:
    tokens: list[str] = []
    for span in CJK_SPAN_RE.findall((text or "").casefold()):
        span_length = len(span)
        if 2 <= span_length <= 8:
            tokens.append(span)
        max_size = min(4, span_length)
        for size in range(2, max_size + 1):
            for index in range(span_length - size + 1):
                tokens.append(span[index : index + size])
    return tokens


def _normalize_phrase(term: str) -> str:
    ascii_tokens = _tokenize_ascii_text(term)
    cjk_spans = CJK_SPAN_RE.findall((term or "").casefold())
    if ascii_tokens and not cjk_spans:
        return " ".join(ascii_tokens)
    if cjk_spans and not ascii_tokens:
        return "".join(cjk_spans)
    if ascii_tokens or cjk_spans:
        return " ".join(ascii_tokens + cjk_spans)
    return ""


def _phrase_candidates(keywords: tuple[str, ...]) -> tuple[str, ...]:
    phrases: list[str] = []
    seen: set[str] = set()
    for keyword in keywords:
        normalized = _normalize_phrase(keyword)
        if not normalized or normalized in seen:
            continue
        if " " in normalized or re.search(r"[\u4e00-\u9fff]", normalized):
            phrases.append(normalized)
            seen.add(normalized)
    return tuple(phrases)


def _build_phrase_haystacks(text: str) -> tuple[str, str]:
    ascii_tokens = _tokenize_ascii_text(text)
    ascii_haystack = f" {' '.join(ascii_tokens)} " if ascii_tokens else " "
    cjk_haystack = "".join(CJK_SPAN_RE.findall((text or "").casefold()))
    return ascii_haystack, cjk_haystack


def _phrase_in_haystack(phrase: str, ascii_haystack: str, cjk_haystack: str) -> bool:
    if " " in phrase or re.search(r"[a-z0-9]", phrase):
        return f" {phrase} " in ascii_haystack
    return phrase in cjk_haystack


def _extract_phrase_tokens(text: str, phrases: tuple[str, ...]) -> list[str]:
    if not phrases:
        return []
    ascii_haystack, cjk_haystack = _build_phrase_haystacks(text)
    return [
        _phrase_feature_name(phrase)
        for phrase in phrases
        if _phrase_in_haystack(phrase, ascii_haystack, cjk_haystack)
    ]

def _phrase_feature_name(phrase: str) -> str:
    return f"phrase:{phrase.replace(' ', '_')}"


class TfidfLabeler:
    def __init__(self) -> None:
        TfidfVectorizer, LogisticRegression = _load_sklearn_dependencies()
        self._label_specs = LABEL_SPECS
        self._label_keywords = LABEL_KEYWORDS
        self._label_by_key = {spec.key: spec for spec in self._label_specs}
        self._label_token_cues = {
            key: frozenset(_tokenize_text(" ".join(keywords)))
            for key, keywords in self._label_keywords.items()
        }
        self._label_phrase_cues = {
            key: _phrase_candidates(keywords)
            for key, keywords in self._label_keywords.items()
        }
        self._soft_story_tokens = frozenset(_tokenize_text(" ".join(SOFT_STORY_CUES)))
        self._soft_story_phrases = tuple(
            dict.fromkeys(
                normalized
                for cue in SOFT_STORY_CUES
                if (normalized := _normalize_phrase(cue))
            )
        )
        self._all_phrase_cues = tuple(
            dict.fromkeys(phrase for phrases in self._label_phrase_cues.values() for phrase in phrases)
        )
        self._prototype_docs = {
            spec.key: (
                f"{spec.prototype} {' '.join(self._label_keywords.get(spec.key, ()))} "
                f"{' '.join(self._label_keywords.get(spec.key, ()))}"
            ).strip()
            for spec in self._label_specs
        }
        self._vectorizer = TfidfVectorizer(
            lowercase=False,
            tokenizer=str.split,
            preprocessor=None,
            token_pattern=None,
            ngram_range=(1, 2),
            sublinear_tf=True,
        )
        self._classifier = LogisticRegression(
            max_iter=1000,
            class_weight="balanced",
        )
        train_documents, train_labels = self._build_training_corpus()
        matrix = self._vectorizer.fit_transform(train_documents)
        self._classifier.fit(matrix, train_labels)
        self._label_classes = tuple(str(value) for value in self._classifier.classes_)

    def _weighted_tokens(self, text: str, weight: int, phrases: tuple[str, ...] | None = None) -> list[str]:
        base_tokens = _tokenize_text(text)
        phrase_tokens = _extract_phrase_tokens(text, phrases or self._all_phrase_cues)
        weighted = base_tokens + phrase_tokens
        if not weighted:
            return []
        return weighted * max(1, weight)

    def _feature_document(
        self,
        title: str,
        summary: str = "",
        publisher: str = "",
        *,
        title_weight: int = 3,
        summary_weight: int = 1,
        publisher_weight: int = 1,
        phrases: tuple[str, ...] | None = None,
    ) -> str:
        tokens = self._weighted_tokens(title, weight=title_weight, phrases=phrases)
        if summary:
            tokens.extend(self._weighted_tokens(summary, weight=summary_weight, phrases=phrases))
        if publisher:
            tokens.extend(self._weighted_tokens(publisher, weight=publisher_weight, phrases=phrases))
        if not tokens:
            tokens = self._weighted_tokens(title or summary or publisher, weight=1, phrases=phrases)
        return " ".join(tokens)

    def _build_training_corpus(self) -> tuple[list[str], list[str]]:
        documents: list[str] = []
        labels: list[str] = []
        for spec in self._label_specs:
            phrases = self._label_phrase_cues.get(spec.key, ())
            seeds = [
                spec.prototype,
                self._prototype_docs[spec.key],
                *LABEL_TRAINING_SAMPLES.get(spec.key, ()),
                " ".join(self._label_keywords.get(spec.key, ())),
            ]
            for seed in seeds:
                document = self._feature_document(
                    seed,
                    "",
                    title_weight=2,
                    summary_weight=1,
                    phrases=phrases,
                )
                if not document:
                    continue
                documents.append(document)
                labels.append(spec.key)
        return documents, labels

    def _cue_bonus(
        self,
        title_tokens: frozenset[str],
        summary_tokens: frozenset[str],
        publisher_tokens: frozenset[str],
        title_haystacks: tuple[str, str],
        summary_haystacks: tuple[str, str],
        publisher_haystacks: tuple[str, str],
        label_key: str,
    ) -> float:
        cue_tokens = self._label_token_cues.get(label_key, frozenset())
        cue_phrases = self._label_phrase_cues.get(label_key, ())

        title_token_hits = len(title_tokens & cue_tokens)
        summary_token_hits = len(summary_tokens & cue_tokens)
        publisher_token_hits = len(publisher_tokens & cue_tokens)

        title_ascii, title_cjk = title_haystacks
        summary_ascii, summary_cjk = summary_haystacks
        publisher_ascii, publisher_cjk = publisher_haystacks
        title_phrase_hits = sum(1 for phrase in cue_phrases if _phrase_in_haystack(phrase, title_ascii, title_cjk))
        summary_phrase_hits = sum(1 for phrase in cue_phrases if _phrase_in_haystack(phrase, summary_ascii, summary_cjk))
        publisher_phrase_hits = sum(
            1 for phrase in cue_phrases if _phrase_in_haystack(phrase, publisher_ascii, publisher_cjk)
        )

        bonus = 0.0
        bonus += min(0.36, title_token_hits * 0.05)
        bonus += min(0.24, summary_token_hits * 0.03)
        bonus += min(0.12, publisher_token_hits * 0.02)
        bonus += min(0.32, title_phrase_hits * 0.14)
        bonus += min(0.18, summary_phrase_hits * 0.08)
        bonus += min(0.08, publisher_phrase_hits * 0.04)

        if label_key == "soft" and title_phrase_hits:
            bonus += 0.06
            soft_title_token_hits = len(title_tokens & self._soft_story_tokens)
            soft_summary_token_hits = len(summary_tokens & self._soft_story_tokens)
            soft_publisher_token_hits = len(publisher_tokens & self._soft_story_tokens)
            soft_title_phrase_hits = sum(
                1 for phrase in self._soft_story_phrases if _phrase_in_haystack(phrase, title_ascii, title_cjk)
            )
            soft_summary_phrase_hits = sum(
                1 for phrase in self._soft_story_phrases if _phrase_in_haystack(phrase, summary_ascii, summary_cjk)
            )
            soft_publisher_phrase_hits = sum(
                1
                for phrase in self._soft_story_phrases
                if _phrase_in_haystack(phrase, publisher_ascii, publisher_cjk)
            )
            bonus += min(0.24, soft_title_phrase_hits * 0.10)
            bonus += min(0.16, soft_summary_phrase_hits * 0.05)
            bonus += min(0.08, soft_publisher_phrase_hits * 0.04)
            bonus += min(0.14, soft_title_token_hits * 0.03)
            bonus += min(0.10, soft_summary_token_hits * 0.02)
            bonus += min(0.04, soft_publisher_token_hits * 0.01)
            if soft_title_phrase_hits + soft_summary_phrase_hits + soft_publisher_phrase_hits >= 2:
                bonus += 0.12

        return bonus

    def annotate_items(self, items: list[object], batch_size: int = 32) -> list[object]:
        del batch_size
        if not items:
            return items

        feature_documents: list[str] = []
        item_features: list[
            tuple[
                frozenset[str],
                frozenset[str],
                frozenset[str],
                tuple[str, str],
                tuple[str, str],
                tuple[str, str],
            ]
        ] = []
        for item in items:
            title = getattr(item, "title", "")
            summary = getattr(item, "summary", "")
            publisher = getattr(item, "publisher", "")
            title_tokens = frozenset(_tokenize_text(title))
            summary_tokens = frozenset(_tokenize_text(summary))
            publisher_tokens = frozenset(_tokenize_text(publisher))
            title_haystacks = _build_phrase_haystacks(title)
            summary_haystacks = _build_phrase_haystacks(summary)
            publisher_haystacks = _build_phrase_haystacks(publisher)

            title_weight = 3
            summary_weight = 1
            publisher_weight = 1
            if summary:
                title_signal_tokens = len(title_tokens)
                if title_signal_tokens <= 2:
                    title_weight = 1
                    summary_weight = 3
                elif title_signal_tokens <= 4:
                    title_weight = 2
                    summary_weight = 2

            feature_documents.append(
                self._feature_document(
                    title,
                    summary,
                    publisher,
                    title_weight=title_weight,
                    summary_weight=summary_weight,
                    publisher_weight=publisher_weight,
                )
            )
            item_features.append(
                (
                    title_tokens,
                    summary_tokens,
                    publisher_tokens,
                    title_haystacks,
                    summary_haystacks,
                    publisher_haystacks,
                )
            )

        probability_rows = self._classifier.predict_proba(
            self._vectorizer.transform(feature_documents)
        )
        classifier_baseline = 1.0 / len(self._label_classes)

        for row_index, item in enumerate(items):
            (
                title_tokens,
                summary_tokens,
                publisher_tokens,
                title_haystacks,
                summary_haystacks,
                publisher_haystacks,
            ) = item_features[row_index]
            probability_by_label = {
                label_key: float(probability_rows[row_index][class_index])
                for class_index, label_key in enumerate(self._label_classes)
            }
            best_key = ""
            best_name = ""
            best_score = -1.0
            for spec in self._label_specs:
                score = probability_by_label.get(spec.key, classifier_baseline)
                score += self._cue_bonus(
                    title_tokens,
                    summary_tokens,
                    publisher_tokens,
                    title_haystacks,
                    summary_haystacks,
                    publisher_haystacks,
                    spec.key,
                )
                if score > best_score:
                    best_key = spec.key
                    best_name = self._label_by_key[spec.key].label
                    best_score = score

            item.content_label = best_key
            item.content_label_name = best_name
            item.content_label_score = max(0.0, float(best_score))

        return items


@lru_cache(maxsize=8)
def get_semantic_labeler(
    model_dir: str | None = None,
    backend: str = "model",
) -> SemanticLabeler | TfidfLabeler:
    if backend == "model":
        resolved = ensure_model_downloaded(model_dir)
        return SemanticLabeler(resolved)
    if backend == "tfidf":
        return TfidfLabeler()
    raise SemanticError(f"不支持的过滤模式: {backend}")
