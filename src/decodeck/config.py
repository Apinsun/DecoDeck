"""Configuration loading for DecoDeck."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path

DEFAULT_CONFIG_PATH = Path("config.toml")

#: Preset base URLs for well-known OpenAI-compatible providers.
PROVIDER_BASE_URLS = {
    "ollama": "http://localhost:11434/v1",
    "vllm": "http://localhost:8000/v1",
    "openai": "https://api.openai.com/v1",
}


@dataclass(frozen=True)
class ModelConfig:
    provider: str
    model: str
    base_url: str
    api_key: str
    thinking: bool | None = None  # None = défaut du modèle, False = désactivé


@dataclass(frozen=True)
class Config:
    model: ModelConfig


def load_config(path: Path = DEFAULT_CONFIG_PATH) -> Config:
    """Load the configuration from a TOML file."""
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    model = data.get("model", {})

    provider = model.get("provider", "ollama")
    base_url = model.get("base_url") or PROVIDER_BASE_URLS.get(provider, "")

    thinking = model.get("thinking")

    return Config(
        model=ModelConfig(
            provider=provider,
            model=model.get("model", ""),
            base_url=base_url,
            api_key=model.get("api_key", ""),
            thinking=thinking if isinstance(thinking, bool) else None,
        )
    )
