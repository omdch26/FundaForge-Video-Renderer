"""Config loading and path resolution.

Why this exists as its own module: every stage needs SYSTEM_ROOT resolved and the
read-only boundary enforced. Doing it once here means no stage can accidentally
write outside the repo.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path

import yaml
from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parent.parent


@dataclass(frozen=True)
class Config:
    system_root: Path
    pipeline: dict
    lanes: dict
    brand: dict
    pronunciation: dict

    # ---- read-only inputs ------------------------------------------------
    def ro(self, key: str) -> Path:
        """Resolve a read-only input path under SYSTEM_ROOT."""
        return self.system_root / self.pipeline["paths"][key]

    # ---- writeable outputs -----------------------------------------------
    def out_dir(self, unit_id: str) -> Path:
        d = REPO_ROOT / self.pipeline["paths"]["output"] / unit_id
        d.mkdir(parents=True, exist_ok=True)
        return d

    def assert_writeable(self, path: Path) -> None:
        """Guard against the one mistake that would be genuinely damaging.

        The carousel system shares this folder tree. Writing outside the repo could
        change a rendered PDF that is already scheduled. Fail loudly instead.
        """
        resolved = Path(path).resolve()
        if REPO_ROOT not in resolved.parents and resolved != REPO_ROOT:
            raise PermissionError(
                f"Refusing to write outside the repo: {resolved}\n"
                f"Everything above {REPO_ROOT} is read-only. "
                f"If this is carousel feedback, append to Carousel_Feedback_Log.md instead."
            )

    def lane(self, lane_name: str) -> dict:
        try:
            return self.lanes[lane_name]
        except KeyError:
            raise KeyError(f"Unknown lane {lane_name!r}. Expected 'season' or 'blueprint'.")

    def accent_hex(self, lane_name: str) -> str:
        return self.brand["palette"][self.lane(lane_name)["accent"]]


def load() -> Config:
    load_dotenv(REPO_ROOT / ".env")

    system_root = os.getenv("SYSTEM_ROOT")
    if not system_root:
        raise RuntimeError("SYSTEM_ROOT is not set. Copy .env.example to .env and fill it in.")

    def _yaml(name: str) -> dict:
        return yaml.safe_load((REPO_ROOT / "config" / name).read_text(encoding="utf-8"))

    def _json(name: str) -> dict:
        return json.loads((REPO_ROOT / "config" / name).read_text(encoding="utf-8"))

    return Config(
        system_root=Path(system_root),
        pipeline=_yaml("pipeline.yaml"),
        lanes=_yaml("lanes.yaml"),
        brand=_json("brand.json"),
        pronunciation=_json("pronunciation.json"),
    )
