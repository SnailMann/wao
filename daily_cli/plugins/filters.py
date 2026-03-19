from __future__ import annotations

from dataclasses import dataclass

from ..runtime.semantic import MODEL_REPO_ID, TFIDF_BACKEND_ID, get_semantic_labeler, list_filter_backends


@dataclass(frozen=True)
class FilterPlugin:
    key: str
    label: str
    model_name: str


FILTER_PLUGINS = {
    "tfidf": FilterPlugin(
        key="tfidf",
        label="TF-IDF + LogisticRegression",
        model_name=TFIDF_BACKEND_ID,
    ),
    "model": FilterPlugin(
        key="model",
        label="Embedding model",
        model_name=MODEL_REPO_ID,
    ),
}


def list_filter_modes() -> tuple[str, ...]:
    return list_filter_backends()


def get_filter_plugin(key: str) -> FilterPlugin:
    try:
        return FILTER_PLUGINS[key]
    except KeyError as exc:
        raise ValueError(f"不支持的过滤模式: {key}") from exc


def annotate_items(
    items: list[object],
    *,
    filter_mode: str,
    semantic_model_dir: str | None,
) -> None:
    if not items:
        return
    labeler = get_semantic_labeler(semantic_model_dir, backend=filter_mode)
    labeler.annotate_items(items)
