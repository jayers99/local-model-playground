"""Profile loading for the gcp-agent CLI."""
from __future__ import annotations

from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field


class Profile(BaseModel):
    name: str
    description: str
    runtime: Literal["mlx"]
    model: str
    host: str = "127.0.0.1"
    port: int = 8080
    base_url: str
    temperature: float = 0.3
    max_tokens: int = 4000
    intended_use: list[str] = Field(default_factory=list)


def load(name: str, profiles_dir: Path = Path("profiles")) -> Profile:
    path = profiles_dir / f"{name}.yaml"
    if not path.exists():
        raise FileNotFoundError(
            f"Profile '{name}' not found at {path}"
        )
    data = yaml.safe_load(path.read_text())
    return Profile.model_validate(data)
