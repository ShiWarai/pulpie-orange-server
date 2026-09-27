"""Загрузка config.yaml."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

PROJECT_ROOT = Path(__file__).resolve().parent.parent


@dataclass(frozen=True)
class ServerConfig:
    host: str
    port: int


@dataclass(frozen=True)
class ModelConfig:
    path: Path


@dataclass(frozen=True)
class ExtractionConfig:
    max_input_bytes: int
    default_max_tokens: int
    default_device: str


@dataclass(frozen=True)
class HttpConfig:
    ssl_verify: bool


@dataclass(frozen=True)
class ApiConfig:
    key: str


@dataclass(frozen=True)
class AppConfig:
    server: ServerConfig
    model: ModelConfig
    extraction: ExtractionConfig
    http: HttpConfig
    api: ApiConfig


def _resolve_path(raw: str) -> Path:
    p = Path(raw)
    if p.is_absolute():
        return p
    return (PROJECT_ROOT / p).resolve()


def load_config(path: str | Path | None = None) -> AppConfig:
    config_path = Path(path) if path else PROJECT_ROOT / "config.yaml"
    with config_path.open(encoding="utf-8") as f:
        data: dict[str, Any] = yaml.safe_load(f) or {}

    server = data.get("server") or {}
    model = data.get("model") or {}
    extraction = data.get("extraction") or {}
    http = data.get("http") or {}
    api = data.get("api") or {}
    api_key = os.environ.get("API_KEY", "").strip() or str(api.get("key") or "").strip()

    return AppConfig(
        server=ServerConfig(
            host=str(server.get("host", "0.0.0.0")),
            port=int(server.get("port", 5000)),
        ),
        model=ModelConfig(path=_resolve_path(str(model.get("path", "model")))),
        extraction=ExtractionConfig(
            max_input_bytes=int(extraction.get("max_input_bytes", 5_000_000)),
            default_max_tokens=int(extraction.get("default_max_tokens", 1024)),
            default_device=str(extraction.get("default_device", "auto")),
        ),
        http=HttpConfig(ssl_verify=bool(http.get("ssl_verify", False))),
        api=ApiConfig(key=api_key),
    )
