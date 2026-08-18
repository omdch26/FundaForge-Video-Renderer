"""G-Humanization — mechanical half of CLAUDE.md Section XI, deterministic only.

WHY THIS EXISTS
----------------
All on-screen/voiceover text is public-facing and must sound human, not
AI-generated, per 00_System_Context/CLAUDE.md Section XI (Humanization
Standard). Generation is now Claude drafting freely in Cowork chat, not a
fixed template, so nothing else in the pipeline enforces this.

WHAT THIS DOES NOT DO
----------------------
Section XI splits into a mechanical half (banned patterns: triplets,
inflated words, artificial parallelism, corporate jargon) and a judgement
half (does it actually read in Sri's voice, checked against
Founder_Voice_Sample.md). This module checks ONLY the mechanical half.
Whether a three-item list is a lazy triplet or three genuinely separate
ideas, and whether prose "sounds like Sri," are calls Section XI itself
defers to a human read — a pattern-matcher can find the shape, not rule on
the exception. Do not extend this module to attempt that half.

Findings are WARN only, for the same reason the fidelity gate keeps its own
heuristic checks advisory: a triplet detector will sometimes flag three
genuinely distinct ideas, and a banned-word list will sometimes flag a word
used in a different, legitimate sense. A human reads the warning and
decides; this gate does not block a build on it.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

# Exact list from 00_System_Context/CLAUDE.md Section XI. Do not add to this
# list without updating that section first — it is the source of truth.
BANNED_PHRASES = {
    "innovative", "transformative", "groundbreaking",
    "leveraging", "synergies", "best practices",
}

_TRIPLET_PATTERN = re.compile(
    r"\b\w[\w\s]*?,\s*\w[\w\s]*?,?\s+and\s+\w[\w\s]*?[.,]")

_PARALLELISM_PATTERN = re.compile(
    r"\bit'?s\s+not\s+[^,]+,\s*(?:but\s+)?it'?s\s+[^.]+", re.IGNORECASE)


@dataclass
class Finding:
    severity: str        # always 'warn' for this gate — see module docstring
    code: str
    message: str


def _scene_text(scene: dict) -> str:
    return f"{scene.get('headline', '')} {scene.get('body', '')}"


def check(script: dict) -> list[Finding]:
    """Check a shot plan's on-screen text for Section XI's banned mechanical
    patterns. `script` is the shot-plan dict — reads scenes[].headline and
    scenes[].body directly, the same fields the shotlist schema defines.
    """
    findings: list[Finding] = []

    for scene in script.get("scenes", []):
        text = _scene_text(scene)
        scene_id = scene.get("scene_id", "?")

        for m in _TRIPLET_PATTERN.finditer(text):
            findings.append(Finding(
                "warn", "POSSIBLE_TRIPLET",
                f"Scene {scene_id}: possible triplet ({m.group(0).strip()!r}). "
                f"Fine if genuinely three separate ideas — flag for a human read."))

        lowered = text.lower()
        for phrase in BANNED_PHRASES:
            if phrase in lowered:
                findings.append(Finding(
                    "warn", "BANNED_PHRASE",
                    f"Scene {scene_id}: contains {phrase!r} — banned inflated/corporate "
                    f"language per Section XI."))

        for m in _PARALLELISM_PATTERN.finditer(text):
            findings.append(Finding(
                "warn", "ARTIFICIAL_PARALLELISM",
                f"Scene {scene_id}: artificial parallelism ({m.group(0).strip()!r}). "
                f"Section XI flags \"it's not X, it's Y\" constructions."))

    return findings


def passed(findings: list[Finding]) -> bool:
    return not any(f.severity == "fail" for f in findings)
