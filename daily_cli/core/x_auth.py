from __future__ import annotations

from dataclasses import dataclass
import os

from .config import config_file, read_json_file, write_json_file

X_TOKEN_ENV_VARS = ("X_BEARER_TOKEN", "TWITTER_BEARER_TOKEN")


@dataclass(frozen=True)
class XTokenState:
    token: str
    source: str
    path: str = ""

    @property
    def masked_token(self) -> str:
        if len(self.token) <= 8:
            return "*" * len(self.token)
        return f"{self.token[:4]}...{self.token[-4:]}"


def x_token_file():
    return config_file("x_token.json")


def save_x_bearer_token(token: str) -> XTokenState:
    value = token.strip()
    if not value:
        raise ValueError("X Bearer Token 不能为空")
    path = x_token_file()
    write_json_file(path, {"bearer_token": value}, private=True)
    return XTokenState(token=value, source="config", path=str(path))


def load_saved_x_bearer_token() -> XTokenState | None:
    path = x_token_file()
    payload = read_json_file(path, default=None)
    if not payload:
        return None
    token = str(payload.get("bearer_token") or "").strip()
    if not token:
        return None
    return XTokenState(token=token, source="config", path=str(path))


def clear_saved_x_bearer_token() -> bool:
    path = x_token_file()
    if not path.exists():
        return False
    path.unlink()
    return True


def resolve_x_bearer_token() -> XTokenState:
    for env_name in X_TOKEN_ENV_VARS:
        token = os.environ.get(env_name, "").strip()
        if token:
            return XTokenState(token=token, source=f"env:{env_name}")

    saved = load_saved_x_bearer_token()
    if saved is not None:
        return saved

    raise ValueError("未配置 X Bearer Token，请先运行 `daily x login` 或设置 X_BEARER_TOKEN")
