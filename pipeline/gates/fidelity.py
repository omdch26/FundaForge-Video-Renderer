"""G1 — Fidelity gate. The most important gate in this pipeline.

WHY THIS EXISTS
---------------
Curriculum Modules 11 and 12 are a paid B2B product. The carousels give the what
and the why; they withhold the how and the evidence. Compression is where that
line breaks: a carousel spends three slides establishing that a problem has no
clean resolution, and a short is tempted to state a flat rule. That flat rule is
exactly the defensible position the carousel deliberately withheld.

A real example this gate was built from. BP34 slide 4 reads:

    "Retention usually wins, NARROWLY. Where a statutory duty to retain exists,
     it GENERALLY overrides an erasure request for THOSE SPECIFIC RECORDS."

A draft script rendered that as "retention wins" — which is a flat rule the
source never gives.

DESIGN NOTE
-----------
The deterministic checks below carry the weight. An LLM judge is ADVISORY ONLY
and must never be the sole gate: a judge at 95% accuracy still leaks roughly four
units across 86, and the leaks concentrate in Blueprints, which is precisely
where the paid product lives. Blueprints additionally require human review —
see lanes.yaml -> blueprint.human_script_review, which must stay true.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

# Words that mark a claim as qualified rather than absolute. If the source hedges
# and the script does not, meaning has been changed, not merely shortened.
HEDGE_MARKERS = {
    "usually", "generally", "normally", "typically", "often", "mostly",
    "narrowly", "partial", "partially", "rarely", "seldom",
    "it depends", "depends who", "depends on",
    "both sides", "both marked", "arguing both", "either way",
    "no clean resolution", "no easy answer", "not every", "no single",
    "tends to", "can be", "may be", "might", "roughly", "approximately",
    "in most", "in general", "as a rule", "broadly",
    "specific records", "those specific", "only those",
    "honest answer", "defensible", "a position you take",
}

# Absolutes that a compressed script reaches for when it drops a hedge.
FLATTENING_MARKERS = {
    "always", "never", "must always", "the correct answer is",
    "the answer is", "the rule is", "simply", "just", "all you need",
    "guaranteed", "in every case", "without exception", "the only",
}


@dataclass
class Finding:
    severity: str        # 'fail' | 'warn'
    code: str
    message: str


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").lower())


def _markers_present(text: str, markers: set[str]) -> set[str]:
    t = _norm(text)
    return {m for m in markers if m in t}


def check(unit, script: dict) -> list[Finding]:
    """Compare a generated script against its source CSV.

    `unit` is a pipeline.source.Unit. `script` is the generated script dict with
    at least: {'scenes': [{'slide_refs': [...], 'voiceover': str}], 'lane': str}
    """
    findings: list[Finding] = []

    source_text = " ".join(f"{s.header_text} {s.body_text}" for s in unit.slides)
    script_text = " ".join(sc.get("voiceover", "") for sc in script.get("scenes", []))

    # --- 1. Hedge preservation. Hard fail. --------------------------------
    src_hedges = _markers_present(source_text, HEDGE_MARKERS)
    scr_hedges = _markers_present(script_text, HEDGE_MARKERS)
    if src_hedges and not scr_hedges:
        findings.append(Finding(
            "fail", "HEDGE_DROPPED",
            f"Source hedges ({sorted(src_hedges)}) but the script carries none. "
            f"Compression has turned a qualified claim into a flat rule."))

    # --- 2. Flattening language that the source never used. Hard fail. ----
    introduced = _markers_present(script_text, FLATTENING_MARKERS) - _markers_present(source_text, FLATTENING_MARKERS)
    if introduced:
        findings.append(Finding(
            "fail", "ABSOLUTE_INTRODUCED",
            f"Script introduces absolutes the source avoids: {sorted(introduced)}."))

    # --- 3. The trap slide must survive intact. Hard fail. ----------------
    trap = unit.trap_slide
    trap_hedges = _markers_present(f"{trap.header_text} {trap.body_text}", HEDGE_MARKERS)
    trap_scenes = [sc for sc in script.get("scenes", []) if 9 in sc.get("slide_refs", [])]
    if not trap_scenes:
        findings.append(Finding("fail", "TRAP_MISSING", "Slide 9 is not covered by any scene."))
    elif trap_hedges:
        trap_script = " ".join(sc.get("voiceover", "") for sc in trap_scenes)
        if not _markers_present(trap_script, HEDGE_MARKERS):
            findings.append(Finding(
                "fail", "TRAP_FLATTENED",
                f"Slide 9 hedges ({sorted(trap_hedges)}) but its scene states a flat position. "
                f"This is the single most damaging failure mode in the pipeline."))

    # --- 4. Hook must be verbatim. Hard fail. -----------------------------
    # Slide 1 hooks are 4-6 words, written for a cold scroll at thumbnail size,
    # and caught real problems across five consecutive builds. Not ours to rewrite.
    first = next((sc for sc in script.get("scenes", []) if 1 in sc.get("slide_refs", [])), None)
    if first is None:
        findings.append(Finding("fail", "HOOK_MISSING", "Slide 1 is not covered by any scene."))
    else:
        hook = _norm(unit.hook_slide1).rstrip(".")
        if hook not in _norm(first.get("voiceover", "")):
            findings.append(Finding(
                "fail", "HOOK_REWRITTEN",
                f"Opening line must contain the slide 1 hook verbatim: {unit.hook_slide1!r}"))

    # --- 5. Claim coverage. Warn. -----------------------------------------
    uncovered = [
        s.slide_number for s in unit.slides
        if not any(s.slide_number in sc.get("slide_refs", []) for sc in script.get("scenes", []))
    ]
    if uncovered:
        sev = "fail" if any(n in (1, 9) for n in uncovered) else "warn"
        findings.append(Finding(sev, "SLIDE_UNCOVERED", f"Slides not represented: {uncovered}"))

    # --- 6. Instagram mechanics must not leak through. Hard fail. ---------
    for banned, code in ((r"\bcomment\s+[A-Z]{3,}\b", "IG_KEYWORD"),
                         (r"\binstagram\b", "IG_REFERENCE"),
                         (r"\bsave (this|it)\b", "IG_SAVE")):
        if re.search(banned, script_text, re.IGNORECASE):
            findings.append(Finding(
                "fail", code,
                f"Script contains an Instagram-only mechanic ({code}). "
                f"YouTube CTAs are tier 1-3 only; the comment-keyword mechanic does not port."))

    return findings


def passed(findings: list[Finding]) -> bool:
    return not any(f.severity == "fail" for f in findings)
