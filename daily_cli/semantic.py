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
        "boyfriend",
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


def list_content_labels() -> tuple[str, ...]:
    return tuple(spec.key for spec in LABEL_SPECS)


def list_filter_backends() -> tuple[str, ...]:
    return FILTER_BACKENDS


def get_content_label_name(key: str) -> str:
    spec = LABEL_SPEC_BY_KEY.get(key)
    return spec.label if spec is not None else key


def default_model_dir() -> Path:
    return Path.home() / ".cache" / "daily-cli" / "models" / MODEL_CACHE_DIRNAME


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
            "语义过滤依赖未安装，请先执行 `python3 -m pip install .` 安装完整依赖。"
        ) from exc
    transformers_logging.set_verbosity_error()
    return torch, functional, AutoModel, AutoTokenizer


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

    headers = {"User-Agent": "daily-cli/0.1"}
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
    target_dir = Path(model_dir).expanduser() if model_dir else default_model_dir()
    missing = [name for name in REQUIRED_MODEL_FILES if not (target_dir / name).exists()]
    if missing:
        joined = ", ".join(missing)
        raise SemanticError(
            "语义模型尚未准备好，请先运行 `daily-cli model download`。"
            f" 当前目录缺少: {joined}"
        )
    return str(target_dir)


def download_model(model_dir: str | None = None, force: bool = False) -> str:
    target_dir = Path(model_dir).expanduser() if model_dir else default_model_dir()
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
    return [f"phrase:{phrase}" for phrase in phrases if _phrase_in_haystack(phrase, ascii_haystack, cjk_haystack)]


class TfidfLabeler:
    def __init__(self) -> None:
        self._label_specs = LABEL_SPECS
        self._label_keywords = LABEL_KEYWORDS
        self._label_token_cues = {
            key: frozenset(_tokenize_text(" ".join(keywords)))
            for key, keywords in self._label_keywords.items()
        }
        self._label_phrase_cues = {
            key: _phrase_candidates(keywords)
            for key, keywords in self._label_keywords.items()
        }
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
        self._idf, self._prototype_vectors = self._build_prototypes()

    def _build_prototypes(self) -> tuple[dict[str, float], dict[str, dict[str, float]]]:
        doc_tokens: dict[str, list[str]] = {
            key: self._weighted_tokens(text, weight=2, phrases=self._label_phrase_cues.get(key, ()))
            for key, text in self._prototype_docs.items()
        }
        document_count = len(doc_tokens)
        document_frequency: Counter[str] = Counter()
        for tokens in doc_tokens.values():
            document_frequency.update(set(tokens))

        idf = {
            token: math.log((1 + document_count) / (1 + frequency)) + 1.0
            for token, frequency in document_frequency.items()
        }
        prototype_vectors = {
            key: self._normalize_vector(self._tfidf_vector(tokens, idf))
            for key, tokens in doc_tokens.items()
        }
        return idf, prototype_vectors

    def _tfidf_vector(self, tokens: list[str], idf: dict[str, float]) -> dict[str, float]:
        counts = Counter(token for token in tokens if token in idf)
        if not counts:
            return {}
        token_count = sum(counts.values())
        return {
            token: (count / token_count) * idf[token]
            for token, count in counts.items()
        }

    def _normalize_vector(self, vector: dict[str, float]) -> dict[str, float]:
        magnitude = math.sqrt(sum(value * value for value in vector.values()))
        if magnitude <= 0:
            return {}
        return {
            token: value / magnitude
            for token, value in vector.items()
        }

    def _cosine_similarity(self, left: dict[str, float], right: dict[str, float]) -> float:
        if not left or not right:
            return 0.0
        if len(left) > len(right):
            left, right = right, left
        return sum(value * right.get(token, 0.0) for token, value in left.items())

    def _weighted_tokens(self, text: str, weight: int, phrases: tuple[str, ...] | None = None) -> list[str]:
        base_tokens = _tokenize_text(text)
        phrase_tokens = _extract_phrase_tokens(text, phrases or self._all_phrase_cues)
        weighted = base_tokens + phrase_tokens
        if not weighted:
            return []
        return weighted * max(1, weight)

    def _cue_bonus(
        self,
        title_tokens: frozenset[str],
        summary_tokens: frozenset[str],
        title_haystacks: tuple[str, str],
        summary_haystacks: tuple[str, str],
        label_key: str,
    ) -> float:
        cue_tokens = self._label_token_cues.get(label_key, frozenset())
        cue_phrases = self._label_phrase_cues.get(label_key, ())

        title_token_hits = len(title_tokens & cue_tokens)
        summary_token_hits = len(summary_tokens & cue_tokens)

        title_ascii, title_cjk = title_haystacks
        summary_ascii, summary_cjk = summary_haystacks
        title_phrase_hits = sum(1 for phrase in cue_phrases if _phrase_in_haystack(phrase, title_ascii, title_cjk))
        summary_phrase_hits = sum(1 for phrase in cue_phrases if _phrase_in_haystack(phrase, summary_ascii, summary_cjk))

        bonus = 0.0
        bonus += min(0.36, title_token_hits * 0.05)
        bonus += min(0.24, summary_token_hits * 0.03)
        bonus += min(0.32, title_phrase_hits * 0.14)
        bonus += min(0.18, summary_phrase_hits * 0.08)

        if label_key == "soft" and title_phrase_hits:
            bonus += 0.06

        return bonus

    def annotate_items(self, items: list[object], batch_size: int = 32) -> list[object]:
        del batch_size
        for item in items:
            title = getattr(item, "title", "")
            summary = getattr(item, "summary", "")
            title_tokens = frozenset(_tokenize_text(title))
            summary_tokens = frozenset(_tokenize_text(summary))
            title_haystacks = _build_phrase_haystacks(title)
            summary_haystacks = _build_phrase_haystacks(summary)
            tokens = self._weighted_tokens(title, weight=3)
            tokens.extend(self._weighted_tokens(summary, weight=1))
            if not tokens:
                tokens = self._weighted_tokens(title or summary, weight=1)
            vector = self._normalize_vector(self._tfidf_vector(tokens, self._idf))

            best_key = ""
            best_name = ""
            best_score = -1.0
            for spec in self._label_specs:
                score = self._cosine_similarity(vector, self._prototype_vectors[spec.key])
                score += self._cue_bonus(
                    title_tokens,
                    summary_tokens,
                    title_haystacks,
                    summary_haystacks,
                    spec.key,
                )
                if score > best_score:
                    best_key = spec.key
                    best_name = spec.label
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
