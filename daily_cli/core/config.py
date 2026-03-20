from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


def default_config_dir() -> Path:
    xdg_home = os.environ.get("XDG_CONFIG_HOME", "").strip()
    if xdg_home:
        return Path(xdg_home).expanduser() / "daily"
    return Path.home() / ".config" / "daily"


def config_file(name: str) -> Path:
    return default_config_dir() / name


def read_json_file(path: Path, *, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"配置文件损坏: {path}") from exc


def write_json_file(path: Path, payload: Any, *, private: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if private:
        path.chmod(0o600)
