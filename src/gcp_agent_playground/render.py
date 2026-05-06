"""Markdown output rendering for review workflows."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from .profiles import Profile

OUTPUTS_DIR = Path("outputs")


def write_review_md(*, body: str, source: Path, profile: Profile,
                    out_dir: Path = OUTPUTS_DIR) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ")
    out_path = out_dir / f"{ts}-review.md"
    header = (
        f"<!--\n"
        f"source: {source}\n"
        f"profile: {profile.name}\n"
        f"model: {profile.model}\n"
        f"timestamp: {ts}\n"
        f"-->\n\n"
    )
    out_path.write_text(header + body)
    return out_path
