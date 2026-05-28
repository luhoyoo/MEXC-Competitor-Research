from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class Competitor:
    name: str
    slug: str
    homepage: str
    blog: str | None = None
    announcement: str | None = None
    x: str | None = None
    instagram: str | None = None


def load_competitors(config_path: Path) -> list[Competitor]:
    text = config_path.read_text(encoding="utf-8")
    raw = load_yaml(text)

    competitors = []
    for item in raw.get("competitors", []):
        competitors.append(
            Competitor(
                name=item["name"],
                slug=item.get("slug") or item["name"].lower().replace(" ", "-"),
                homepage=item["homepage"],
                blog=item.get("blog"),
                announcement=item.get("announcement"),
                x=item.get("x"),
                instagram=item.get("instagram"),
            )
        )
    return competitors


def load_yaml(text: str) -> dict[str, Any]:
    try:
        import yaml

        loaded = yaml.safe_load(text) or {}
        return loaded if isinstance(loaded, dict) else {}
    except ImportError:
        return parse_simple_competitor_yaml(text)


def parse_simple_competitor_yaml(text: str) -> dict[str, Any]:
    competitors: list[dict[str, str]] = []
    current: dict[str, str] | None = None

    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or stripped == "competitors:":
            continue
        if stripped.startswith("- "):
            if current:
                competitors.append(current)
            current = {}
            stripped = stripped[2:].strip()
            if stripped and ":" in stripped:
                key, value = stripped.split(":", 1)
                current[key.strip()] = value.strip().strip('"').strip("'")
            continue
        if current is not None and ":" in stripped:
            key, value = stripped.split(":", 1)
            current[key.strip()] = value.strip().strip('"').strip("'")

    if current:
        competitors.append(current)
    return {"competitors": competitors}
