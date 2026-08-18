"""G2 — Brand gate. Pure assertions, no LLM.

Mirrors the palette guard already in batch_render_season.py: an off-palette fill
fails the build rather than shipping a silently off-brand frame. The carousel
system holds 860 slides consistent this way; the same discipline applies here.

The amber rule is the one that matters. Amber means constraint, warning, trap or
failure mode. It is never decoration. Overloading it destroys a working signal,
and a draft pipeline was caught painting amber onto words like "NOT" and "EXACT"
purely for emphasis.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

HEX = re.compile(r"#[0-9A-Fa-f]{6}")


@dataclass
class Finding:
    severity: str
    code: str
    message: str


def check(cfg, unit, shotlist: dict) -> list[Finding]:
    findings: list[Finding] = []
    palette = {v.lower() for v in cfg.brand["palette"].values()}
    allowed_families = set()
    for f in cfg.brand["fonts"].values():
        allowed_families.add(f["family"])
        allowed_families.update(f.get("aliases", []))

    # --- 1. Every colour is on palette ------------------------------------
    blob = str(shotlist)
    for found in set(HEX.findall(blob)):
        if found.lower() not in palette:
            findings.append(Finding("fail", "OFF_PALETTE",
                f"{found} is not in the locked palette. Allowed: {sorted(palette)}"))

    # --- 2. Lane accent is correct ----------------------------------------
    expected = cfg.accent_hex(unit.lane).lower()
    actual = str(shotlist.get("accent", "")).lower()
    if actual != expected:
        findings.append(Finding("fail", "WRONG_ACCENT",
            f"{unit.lane} must use {expected}, found {actual}. "
            f"Cyan for Seasons, amber for Blueprints, always."))

    # --- 3. Amber is never decoration -------------------------------------
    valid_reasons = set(cfg.brand["semantics"]["amber_means"])
    for scene in shotlist.get("scenes", []):
        for span in scene.get("amber_spans", []):
            if span.get("reason") not in valid_reasons:
                findings.append(Finding("fail", "AMBER_DECORATION",
                    f"Scene {scene.get('scene_id')}: amber span with reason "
                    f"{span.get('reason')!r}. Amber means constraint, warning, trap or "
                    f"failure mode. Never emphasis."))

    for cap in shotlist.get("captions", []):
        if cap.get("emphasis") == "constraint" and not cap.get("reason"):
            findings.append(Finding("warn", "AMBER_CAPTION_UNJUSTIFIED",
                f"Caption {cap.get('text')!r} is amber with no stated reason."))

    # --- 4. Fonts ---------------------------------------------------------
    for fam in set(re.findall(r'font-family="([^",]+)', blob)):
        if fam.strip() not in allowed_families:
            findings.append(Finding("fail", "OFF_BRAND_FONT",
                f"{fam!r} is not a brand family. Allowed: {sorted(allowed_families)}"))

    # --- 5. Geometry and duration -----------------------------------------
    v = cfg.pipeline["video"]
    if (shotlist.get("width"), shotlist.get("height")) != (v["width"], v["height"]):
        findings.append(Finding("fail", "WRONG_DIMENSIONS",
            f"Expected {v['width']}x{v['height']}."))

    secs = shotlist.get("duration_frames", 0) / v["fps"]
    if not (v["hard_min_seconds"] <= secs <= v["hard_max_seconds"]):
        findings.append(Finding("fail", "DURATION_OUT_OF_BOUNDS",
            f"{secs:.1f}s is outside {v['hard_min_seconds']}-{v['hard_max_seconds']}s."))

    lane = cfg.lane(unit.lane)
    lo, hi = lane["duration_target"]
    if "duration_warn_below" in lane and secs < lane["duration_warn_below"]:
        findings.append(Finding("warn", "BLUEPRINT_TOO_SHORT",
            f"{secs:.1f}s is under {lane['duration_warn_below']}s for a Blueprint. "
            f"A short Blueprint has almost certainly dropped a caveat — re-read the hedges."))
    if "duration_warn_above" in lane and secs > lane["duration_warn_above"]:
        findings.append(Finding("warn", "SEASON_TOO_LONG",
            f"{secs:.1f}s is over {lane['duration_warn_above']}s for a Season — likely over-explaining."))

    # --- 6. Kicker present ------------------------------------------------
    if not shotlist.get("kicker"):
        findings.append(Finding("fail", "KICKER_MISSING",
            "Every frame carries the series kicker. A short must be unmistakably "
            "one lane or the other."))

    return findings


def passed(findings: list[Finding]) -> bool:
    return not any(f.severity == "fail" for f in findings)
