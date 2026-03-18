from __future__ import annotations

import contextlib
from dataclasses import dataclass
from functools import lru_cache
import io
import os
from pathlib import Path
import shutil
import subprocess
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

MODEL_REPO_ID = "intfloat/multilingual-e5-small"
MODEL_CACHE_DIRNAME = "intfloat__multilingual-e5-small"
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


def list_content_labels() -> tuple[str, ...]:
    return tuple(spec.key for spec in LABEL_SPECS)


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


@lru_cache(maxsize=2)
def get_semantic_labeler(model_dir: str | None = None) -> SemanticLabeler:
    resolved = ensure_model_downloaded(model_dir)
    return SemanticLabeler(resolved)
