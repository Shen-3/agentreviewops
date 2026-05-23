from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError

from agentreview.models import AgentReviewConfig

DEFAULT_CONFIG_PATH = ".agentreview.yml"


class ConfigError(ValueError):
    """Raised when an AgentReviewOps config file cannot be loaded."""


def load_config(path: str | Path = DEFAULT_CONFIG_PATH) -> AgentReviewConfig:
    config_path = Path(path)
    if not config_path.exists():
        return AgentReviewConfig()

    try:
        raw_config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ConfigError(f"Invalid YAML in {config_path}: {exc}") from exc

    if raw_config is None:
        raw_config = {}
    if not isinstance(raw_config, dict):
        raise ConfigError(f"Invalid config in {config_path}: expected a YAML mapping")

    return parse_config(raw_config, source=str(config_path))


def parse_config(raw_config: dict[str, Any], *, source: str = "config") -> AgentReviewConfig:
    try:
        return AgentReviewConfig.model_validate(raw_config)
    except ValidationError as exc:
        raise ConfigError(f"Invalid AgentReviewOps config in {source}: {exc}") from exc
