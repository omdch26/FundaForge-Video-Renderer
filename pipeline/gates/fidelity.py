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

# Numbers and durations a script might invent that the source never stated.
# Broader than digits alone: a fabricated "seven years" is as damaging as a
# fabricated "7 years", and retention-period language is exactly where this
# gate exists to catch invention (see Section XI / commercial boundary).
_NUMBER_PATTERN = re.compile(r"\b\d[\d,]*\.?\d*%?\b")
_SPELLED_DURATION_PATTERN = re.compile(
    r"\b(one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|"
    r"twenty|thirty|forty|fifty|sixty|seventy|eighty|ninety|hundred|thousand"
    r")(?:[\s-]\w+){0,2}[\s-](year|month|day|week)s?\b", re.IGNORECASE)

# Capitalised word runs, excluding sentence-initial position (crude proxy for
# a proper noun / named example). Matches a capital letter NOT preceded by
# sentence-ending punctuation and whitespace (or start of string).
_PROPER_NOUN_PATTERN = re.compile(
    r"(?<![.!?]\s)(?<!^)\b[A-Z][a-z]+(?:\s[A-Z][a-z]+)*\b")


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

    scenes = script.get("scenes", [])
    source_text = " ".join(f"{s.header_text} {s.body_text}" for s in unit.slides)
    script_text = " ".join(sc.get("voiceover", "") for sc in scenes)

    # --- 1. Hedge preservation, PER SLIDE. Hard fail. ----------------------
    # Fixed 18 Aug 2026. Was a single whole-script check: "does hedge language
    # exist anywhere in the source, and anywhere in the script." That let one
    # slide's flattened hedge hide behind any OTHER slide that still hedged
    # normally — confirmed via testing that a script flattening ONLY slide 4
    # ("retention usually wins, narrowly" -> "retention wins") passed silently
    # whenever some other slide (e.g. slide 9) still carried hedge language.
    # Every slide with its own source hedge now gets its own check, using the
    # same "look only at the scene(s) covering this slide" approach the old
    # trap-only check already used correctly — just generalised to all ten.
    for slide in unit.slides:
        slide_hedges = _markers_present(f"{slide.header_text} {slide.body_text}", HEDGE_MARKERS)
        if not slide_hedges:
            continue

        covering = [sc for sc in scenes if slide.slide_number in sc.get("slide_refs", [])]
        if not covering:
            continue  # SLIDE_UNCOVERED (below) already reports missing coverage

        covering_text = " ".join(sc.get("voiceover", "") for sc in covering)
        if not _markers_present(covering_text, HEDGE_MARKERS):
            if slide.slide_number == 9:
                findings.append(Finding(
                    "fail", "TRAP_FLATTENED",
                    f"Slide 9 hedges ({sorted(slide_hedges)}) but its scene states a flat "
                    f"position. This is the single most damaging failure mode in the pipeline."))
            else:
                findings.append(Finding(
                    "fail", "HEDGE_DROPPED",
                    f"Slide {slide.slide_number} hedges ({sorted(slide_hedges)}) but its "
                    f"scene carries none. Compression has turned a qualified claim into a "
                    f"flat rule."))

    # --- 2. Flattening language that the source never used. Hard fail. ----
    introduced = _markers_present(script_text, FLATTENING_MARKERS) - _markers_present(source_text, FLATTENING_MARKERS)
    if introduced:
        findings.append(Finding(
            "fail", "ABSOLUTE_INTRODUCED",
            f"Script introduces absolutes the source avoids: {sorted(introduced)}."))

    # --- 3. The trap slide must be present at all. Hard fail. -------------
    # Flattening is now caught above, per-slide, same as every other slide —
    # this only confirms slide 9 has a scene covering it in the first place.
    trap_scenes = [sc for sc in scenes if 9 in sc.get("slide_refs", [])]
    if not trap_scenes:
        findings.append(Finding("fail", "TRAP_MISSING", "Slide 9 is not covered by any scene."))

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

    findings.extend(check_fabrication(unit, script))

    return findings


def check_fabrication(unit, script: dict) -> list[Finding]:
    """G1 extension — catches invention, not just flattening.

    The existing checks above catch a real claim stated too strongly. They
    cannot catch a NEW claim — a number, statistic, or named example the
    source never had — because it matches no hedge/absolute pattern. Needed
    now specifically because generation is a person (Claude, in Cowork)
    drafting freely against the CSV, not a template filling in fixed slots;
    there is no safe fixed-rule mapping backing this up anymore.

    Deliberately WARN, never FAIL: unlike the marker-based checks above,
    this is pattern/overlap heuristics over free text, and legitimate light
    rephrasing ("seven-year retention" -> "seven years") will trigger false
    positives. Advisory, same as an LLM judge would be — a human reads the
    warning and decides, this gate does not block the build on it.
    """
    findings: list[Finding] = []
    source_corpus = _norm(" ".join(f"{s.header_text} {s.body_text}" for s in unit.slides))

    for scene in script.get("scenes", []):
        voiceover = scene.get("voiceover", "")
        slide_refs = scene.get("slide_refs", [])

        candidates: set[str] = set()
        candidates.update(m.group(0) for m in _NUMBER_PATTERN.finditer(voiceover))
        candidates.update(m.group(0) for m in _SPELLED_DURATION_PATTERN.finditer(voiceover))
        candidates.update(m.group(0) for m in _PROPER_NOUN_PATTERN.finditer(voiceover))

        for candidate in candidates:
            norm_candidate = _norm(candidate)
            if not norm_candidate or len(norm_candidate) < 2:
                continue
            if norm_candidate in source_corpus:
                continue
            findings.append(Finding(
                "warn", "POSSIBLE_FABRICATION",
                f"Scene (slides {slide_refs}) contains {candidate!r}, which does not "
                f"appear in the source CSV text. Confirm this traces back to the unit "
                f"before treating it as fact — may be a fabricated detail."))

    return findings


def passed(findings: list[Finding]) -> bool:
    return not any(f.severity == "fail" for f in findings)
