# Fidelity Extension, Humanization Gate, Plan Validator — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend `pipeline/gates/fidelity.py` with a fabrication check, add `pipeline/gates/humanization.py`, and rewire `produce.py plan` from a stub into a validator for an already-authored shot plan — proven against a hand-authored bad and clean BP34 shot plan.

**Architecture:** Two gate modules (one extended, one new) sharing the existing `Finding`/`passed()` pattern from `fidelity.py`. `produce.py plan` becomes an orchestrator that loads a shot plan, validates it against the schema, and runs both gates, printing a combined report. No generation logic anywhere in this codebase — shot-plan authoring happens in Cowork chat, outside this repo's code.

**Tech Stack:** Python 3.11+, `jsonschema` (already in requirements.txt, already installed), `pytest`.

## Global Constraints

- Do not modify `fidelity.py`'s existing checks 1-6 (hedge preservation, absolute introduction, trap-slide integrity, hook verbatim, claim coverage, Instagram mechanics) — only add alongside them.
- All new checks (fabrication, all of humanization) are `warn` severity, never `fail` — see spec Decisions 1-2. Only the existing fidelity checks and schema validation are fatal.
- `humanization.py`'s banned-word list is exactly: `innovative`, `transformative`, `groundbreaking`, `leveraging`, `synergies`, `best practices` — copied verbatim from `00_System_Context/CLAUDE.md` Section XI, not invented or extended.
- No LLM call anywhere in this codebase for these checks — pattern/overlap-based only.
- `plan --unit <ID>` never generates a shot plan. Missing file → clear message + nonzero exit, full stop.
- `render.py`/`tracker.py`/`script.py`/`assets.py`/`shotlist.py` are out of scope — do not create them in this plan.
- Never write into `03_Scripts_Out/`, `05_Rendered_Carousels/`, `02_Vector_Library/`, `00_System_Context/`, `01_Backlog/`, `04_Brand_Assets/Fonts/` — read-only.
- Writeable scope is this repo (`06_Video_Production/FundaForge-Video-Renderer/`) only.

---

### Task 1: Fabrication check in `pipeline/gates/fidelity.py`

**Files:**
- Modify: `pipeline/gates/fidelity.py`
- Test: `tests/test_fidelity_gate.py`

**Interfaces:**
- Consumes: `pipeline.source.Unit` (has `.slides`, each `Slide` has `.header_text`, `.body_text`), existing `HEDGE_MARKERS`/`FLATTENING_MARKERS`/`_norm`/`_markers_present` helpers already in the file.
- Produces: `check_fabrication(unit, script) -> list[Finding]`, called from inside the existing `check()` function and folded into its returned list. `Finding` dataclass is unchanged (`severity`, `code`, `message`).

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_fidelity_gate.py` (the file already has `_bp34()`, `FakeSlide`, `FakeUnit`, `_script()` helpers — reuse them):

```python
def test_fabricated_number_warns():
    unit = _bp34()
    findings = fidelity.check(unit, _script([
        {"slide_refs": [1], "voiceover": "Delete me. The bank cannot."},
        {"slide_refs": [4], "voiceover":
            "Retention usually wins, narrowly, for those specific records. "
            "The bank must keep them for exactly eleven years."},
        {"slide_refs": [9], "voiceover":
            "Name which records are retained under which duty. It depends who is asking."},
    ]))
    codes = {f.code for f in findings}
    assert "POSSIBLE_FABRICATION" in codes
    warn_findings = [f for f in findings if f.code == "POSSIBLE_FABRICATION"]
    assert all(f.severity == "warn" for f in warn_findings)


def test_no_fabrication_on_faithful_script():
    unit = _bp34()
    findings = fidelity.check(unit, _script([
        {"slide_refs": list(range(1, 9)), "voiceover":
            "Delete me. The bank cannot. Retention usually wins, narrowly, and only for "
            "those specific records."},
        {"slide_refs": [9, 10], "voiceover":
            "Name which records are retained under which duty. It depends who is asking."},
    ]))
    assert "POSSIBLE_FABRICATION" not in {f.code for f in findings}


def test_fabrication_check_is_never_fatal():
    unit = _bp34()
    findings = fidelity.check(unit, _script([
        {"slide_refs": [1], "voiceover": "Delete me. The bank cannot."},
        {"slide_refs": [4], "voiceover":
            "Retention usually wins, narrowly, for those specific records, "
            "for a mandatory period of seven-hundred days."},
        {"slide_refs": [9], "voiceover":
            "Name which records are retained under which duty. It depends who is asking."},
    ]))
    fabrication_findings = [f for f in findings if f.code == "POSSIBLE_FABRICATION"]
    assert fabrication_findings  # the invented duration was caught
    assert all(f.severity == "warn" for f in fabrication_findings)  # never fails the build
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd D:\System_Synthesis\06_Video_Production\FundaForge-Video-Renderer && python -m pytest tests/test_fidelity_gate.py -v`
Expected: the three new tests FAIL (AttributeError or `POSSIBLE_FABRICATION` not found — `check_fabrication` doesn't exist yet), the 4 existing tests still PASS.

- [ ] **Step 3: Implement `check_fabrication`**

Add to `pipeline/gates/fidelity.py`, after the existing `HEDGE_MARKERS`/`FLATTENING_MARKERS` definitions and before `Finding`:

```python
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
```

Then add the function itself, after `check()` and before `passed()`:

```python
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
```

Wire it into `check()` — add one line near the end of the existing function, just before the `return findings` statement:

```python
    findings.extend(check_fabrication(unit, script))

    return findings
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd D:\System_Synthesis\06_Video_Production\FundaForge-Video-Renderer && python -m pytest tests/test_fidelity_gate.py -v`
Expected: all 7 tests PASS (4 original + 3 new).

- [ ] **Step 5: Commit**

```bash
cd D:\System_Synthesis\06_Video_Production\FundaForge-Video-Renderer
git add pipeline/gates/fidelity.py tests/test_fidelity_gate.py
git commit -m "$(cat <<'EOF'
Extend fidelity gate with a fabrication check

Existing checks catch flattening (a real claim stated too strongly);
they cannot catch a new claim the source never had, since generation
is now open-ended LLM drafting, not template-filling. Adds a
pattern-based check for numbers, durations, and proper nouns that
don't trace back to the unit's CSV. WARN severity only, matching the
module's own advisory-only principle for anything short of a precise
deterministic match.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 2: `pipeline/gates/humanization.py`

**Files:**
- Create: `pipeline/gates/humanization.py`
- Test: `tests/test_humanization_gate.py`

**Interfaces:**
- Consumes: a `script` dict shaped `{"scenes": [{"headline": str, "body": str, ...}, ...]}` (the shot-plan's own scene shape, per `schemas/shotlist.schema.json` — NOT the `voiceover`-shaped dict `fidelity.py` uses internally; humanization checks the shot plan's actual on-screen `headline`/`body` fields directly).
- Produces: `Finding` dataclass (same shape as `fidelity.Finding` — `severity`, `code`, `message` — redefined locally in this module, not imported, to keep the two gate modules independently readable, matching how `brand.py` also redefines its own `Finding` rather than importing `fidelity.Finding`), `check(script: dict) -> list[Finding]`, `passed(findings: list[Finding]) -> bool`.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_humanization_gate.py`:

```python
"""Proves the humanization gate catches the mechanical patterns Section XI
bans, without trying to automate the judgement-call half (does it sound
like Sri) that CLAUDE.md explicitly leaves to a human read.
"""
from pipeline.gates import humanization


def _script(scenes):
    return {"scenes": scenes}


def test_triplet_warns():
    findings = humanization.check(_script([
        {"headline": "Fast, reliable, and scalable.", "body": "It just works."},
    ]))
    codes = {f.code for f in findings}
    assert "POSSIBLE_TRIPLET" in codes


def test_banned_word_warns():
    findings = humanization.check(_script([
        {"headline": "An innovative approach.",
         "body": "We are leveraging synergies across the platform."},
    ]))
    codes = {f.code for f in findings}
    assert "BANNED_PHRASE" in codes
    messages = " ".join(f.message for f in findings if f.code == "BANNED_PHRASE")
    assert "leveraging" in messages.lower()
    assert "synergies" in messages.lower()
    assert "innovative" in messages.lower()


def test_artificial_parallelism_warns():
    findings = humanization.check(_script([
        {"headline": "It's not a bug, it's a feature.", "body": "Ship it."},
    ]))
    codes = {f.code for f in findings}
    assert "ARTIFICIAL_PARALLELISM" in codes


def test_clean_text_passes():
    findings = humanization.check(_script([
        {"headline": "Delete me. The bank cannot.",
         "body": "A customer exercises erasure. A separate obligation requires "
                  "the bank to keep transaction records for years."},
    ]))
    assert humanization.passed(findings)


def test_all_findings_are_warn_severity():
    findings = humanization.check(_script([
        {"headline": "Fast, reliable, and scalable, leveraging synergies.",
         "body": "It's not a limitation, it's a feature."},
    ]))
    assert findings  # sanity: something was caught
    assert all(f.severity == "warn" for f in findings)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd D:\System_Synthesis\06_Video_Production\FundaForge-Video-Renderer && python -m pytest tests/test_humanization_gate.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'pipeline.gates.humanization'`.

- [ ] **Step 3: Implement `pipeline/gates/humanization.py`**

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd D:\System_Synthesis\06_Video_Production\FundaForge-Video-Renderer && python -m pytest tests/test_humanization_gate.py -v`
Expected: all 5 tests PASS.

- [ ] **Step 5: Commit**

```bash
cd D:\System_Synthesis\06_Video_Production\FundaForge-Video-Renderer
git add pipeline/gates/humanization.py tests/test_humanization_gate.py
git commit -m "$(cat <<'EOF'
Add humanization gate — mechanical half of Section XI, deterministic

Checks triplets, banned inflated/corporate words (exact list from
CLAUDE.md Section XI), and artificial "it's not X, it's Y"
parallelism. WARN severity only — the judgement half (does it sound
like Sri, is a triplet genuinely three ideas) stays a human read
against Founder_Voice_Sample.md, not something this gate attempts.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 3: Rewire `produce.py plan` as a validator

**Files:**
- Modify: `produce.py`
- Test: `tests/test_plan_validator.py`

**Interfaces:**
- Consumes: `pipeline.config.load()`, `pipeline.source.load_unit()`, `pipeline.gates.fidelity.check()`/`passed()`, `pipeline.gates.humanization.check()`/`passed()`, `pipeline.gates.brand.check()`/`passed()`, `jsonschema.validate()`.
- Produces: `cmd_plan(args) -> int` — exit code 0 if the shot plan is schema-valid and no gate reports a `fail`-severity finding (warns are printed but don't affect the exit code), nonzero otherwise. Prints a human-readable report to stdout.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_plan_validator.py`. This tests the validator logic directly (not via subprocess/CLI) by importing `produce`'s functions, using `tmp_path` and monkeypatching `pipeline.config.REPO_ROOT`-dependent paths where needed — simplest approach: write real shot-plan fixture files under a temp `out/shotplans/` and point the function at them via a small refactor that takes an explicit `out_dir` (see Step 3).

```python
"""Proves produce.py's plan command validates an existing shot plan and
never generates one — schema, fidelity gate (incl. fabrication), humanization
gate, brand gate, all wired together and reported.
"""
import json
from pathlib import Path

import pytest

import produce
from pipeline import config as cfgmod


BP34_SLIDES_TEXT = {
    1: ("Delete me. The bank cannot.",
        "A customer exercises erasure. A separate obligation requires the bank "
        "to keep transaction records for years. Both are law, and they point "
        "opposite ways."),
    4: ("Retention usually wins, narrowly.",
        "Where a statutory duty to retain exists, it generally overrides an "
        "erasure request for those specific records — and only those. The "
        "rest must still go."),
    9: ("Reconcile erasure with seven-year retention.",
        "Name which records are retained under which duty, what was deleted, "
        "and who approved the split. Answers claiming full erasure have not "
        "read the retention rules."),
}


def _shotplan(headline_body_by_scene: dict[int, tuple[str, str]], slide_refs_by_scene: dict[int, list[int]]) -> dict:
    scenes = []
    frame = 0
    for scene_id, (headline, body) in headline_body_by_scene.items():
        scenes.append({
            "scene_id": scene_id,
            "card": "BodyCard" if scene_id not in (1, 9) else ("TitleCard" if scene_id == 1 else "TrapCard"),
            "start_frame": frame,
            "duration_frames": 150,
            "slide_refs": slide_refs_by_scene[scene_id],
            "headline": headline,
            "body": body,
        })
        frame += 150
    return {
        "unit_id": "BP34",
        "lane": "blueprint",
        "kicker": "BANKING-GRADE AI",
        "accent": "#F59E0B",
        "fps": 30,
        "width": 1080,
        "height": 1920,
        "duration_frames": frame,
        "audio": {"voice_file": None, "voice_id": "1aP69VftkGksPi01itpR", "model_id": "eleven_multilingual_v2"},
        "scenes": scenes,
    }


def test_missing_shotplan_reports_clearly_and_fails(tmp_path, capsys):
    cfg = cfgmod.load()
    exit_code = produce.validate_shotplan(cfg, "BP34", shotplans_dir=tmp_path)
    assert exit_code != 0
    out = capsys.readouterr().out
    assert "no shot plan" in out.lower() or "not found" in out.lower()


def test_bad_shotplan_flags_flattening_fabrication_and_humanization(tmp_path, capsys):
    plan = _shotplan(
        {1: BP34_SLIDES_TEXT[1],
         4: ("Retention wins.",
             "The bank must keep records for exactly eleven years, "
             "leveraging its fast, reliable, and scalable archive."),
         9: BP34_SLIDES_TEXT[9]},
        {1: [1], 4: [4], 9: [9]},
    )
    (tmp_path / "BP34_shotplan.json").write_text(json.dumps(plan), encoding="utf-8")

    cfg = cfgmod.load()
    exit_code = produce.validate_shotplan(cfg, "BP34", shotplans_dir=tmp_path)

    out = capsys.readouterr().out
    assert exit_code != 0  # flattening is a hard fail
    assert "TRAP_FLATTENED" in out or "HEDGE_DROPPED" in out
    assert "POSSIBLE_FABRICATION" in out  # the invented "eleven years"
    assert "POSSIBLE_TRIPLET" in out
    assert "leveraging" in out.lower()
    assert "human" in out.lower()  # human_script_review notice still prints


def test_clean_shotplan_passes(tmp_path, capsys):
    plan = _shotplan(BP34_SLIDES_TEXT, {1: [1], 4: [4], 9: [9]})
    (tmp_path / "BP34_shotplan.json").write_text(json.dumps(plan), encoding="utf-8")

    cfg = cfgmod.load()
    exit_code = produce.validate_shotplan(cfg, "BP34", shotplans_dir=tmp_path)

    out = capsys.readouterr().out
    assert exit_code == 0
    assert "human" in out.lower()  # sign-off notice always prints, even on a clean pass
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd D:\System_Synthesis\06_Video_Production\FundaForge-Video-Renderer && python -m pytest tests/test_plan_validator.py -v`
Expected: FAIL — `AttributeError: module 'produce' has no attribute 'validate_shotplan'`.

- [ ] **Step 3: Rewrite `produce.py`**

Replace the full file:

```python
#!/usr/bin/env python
"""FundaForge Video Renderer — single entry point.

    python produce.py doctor
    python produce.py plan   --unit S1E05
    python produce.py run    --unit S1E05
    python produce.py run    --season 1
    python produce.py drift

Script generation happens in Cowork chat, not in this codebase — Claude
reads a unit's CSV directly and drafts its shot-list JSON against
schemas/shotlist.schema.json, writing it to out/shotplans/<unit>_shotplan.json.
`plan` validates that file; it never generates one. See CLAUDE.md's
"Script generation" entry under LOCKED DECISIONS for why.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import jsonschema

from pipeline import config as cfgmod
from pipeline import source
from pipeline.gates import brand, fidelity, humanization

REPO_ROOT = Path(__file__).resolve().parent


def cmd_doctor(_args) -> int:
    """Verify wiring before anything spends a credit."""
    ok = True
    try:
        cfg = cfgmod.load()
    except Exception as e:
        print(f"  FAIL  config: {e}")
        return 1

    print(f"  ok    SYSTEM_ROOT -> {cfg.system_root}")
    for key in ("unit_index", "scripts_out", "vector_library", "fonts"):
        p = cfg.ro(key)
        mark = "ok  " if p.exists() else "FAIL"
        ok &= p.exists()
        print(f"  {mark}  {key:15s} -> {p}")

    for lane in ("season", "blueprint"):
        L = cfg.lane(lane)
        for field in ("voice_id", "model_id"):
            if not L.get(field):
                print(f"  WARN  lanes.yaml {lane}.{field} is empty — required before Phase 3")

    print("\n  TODO: font presence, ElevenLabs key reachability, Remotion install, ffmpeg on PATH")
    return 0 if ok else 1


def _fidelity_script_shape(shotplan: dict) -> dict:
    """Adapt a shot plan's scenes[] into the {"scenes": [{"slide_refs",
    "voiceover"}]} shape gates.fidelity.check() expects. Pure reshaping of
    what's already in the shot plan — introduces no new content.
    """
    return {
        "lane": shotplan.get("lane"),
        "scenes": [
            {
                "slide_refs": sc.get("slide_refs", []),
                "voiceover": f"{sc.get('headline', '')} {sc.get('body', '')}".strip(),
            }
            for sc in shotplan.get("scenes", [])
        ],
    }


def _print_findings(gate_name: str, findings: list) -> None:
    if not findings:
        print(f"  {gate_name}: no findings")
        return
    for f in findings:
        marker = "FAIL" if f.severity == "fail" else "warn"
        print(f"  [{marker}] {gate_name} {f.code}: {f.message}")


def validate_shotplan(cfg, unit_id: str, shotplans_dir: Path | None = None) -> int:
    """Load, schema-validate, and gate-check an already-authored shot plan.

    Never generates a shot plan. Returns 0 if schema-valid and no gate
    reports a fail-severity finding; nonzero otherwise. Warn-severity
    findings are printed but do not affect the return code — they are
    advisory, matching the gates' own documented design (see fidelity.py
    and humanization.py module docstrings).
    """
    shotplans_dir = shotplans_dir or (REPO_ROOT / "out" / "shotplans")
    shotplan_path = shotplans_dir / f"{unit_id}_shotplan.json"

    if not shotplan_path.exists():
        print(f"  No shot plan found for {unit_id} at {shotplan_path}")
        print(f"  Author one in Cowork chat against schemas/shotlist.schema.json, "
              f"then run `plan --unit {unit_id}` again to validate it.")
        return 1

    shotplan = json.loads(shotplan_path.read_text(encoding="utf-8"))

    schema = json.loads((REPO_ROOT / "schemas" / "shotlist.schema.json").read_text(encoding="utf-8"))
    try:
        jsonschema.validate(shotplan, schema)
        print(f"  schema: valid")
    except jsonschema.ValidationError as e:
        print(f"  [FAIL] schema: {e.message} (at {list(e.path)})")
        return 1

    unit = source.load_unit(cfg, unit_id)

    if unit.ig_status.lower() != "published":
        print(f"  WARN  {unit_id} is not yet published on Instagram (ig_status={unit.ig_status!r})")

    fidelity_script = _fidelity_script_shape(shotplan)
    fidelity_findings = fidelity.check(unit, fidelity_script)
    _print_findings("fidelity", fidelity_findings)

    humanization_findings = humanization.check(shotplan)
    _print_findings("humanization", humanization_findings)

    brand_findings = brand.check(cfg, unit, shotplan)
    _print_findings("brand", brand_findings)

    any_fail = (
        not fidelity.passed(fidelity_findings)
        or not brand.passed(brand_findings)
    )
    # humanization is warn-only by construction; passed() is still called
    # for symmetry and to catch a future change to its severity policy.
    any_fail = any_fail or not humanization.passed(humanization_findings)

    lane_cfg = cfg.lane(unit.lane)
    if lane_cfg.get("human_script_review"):
        print(f"\n  *** HUMAN SCRIPT REVIEW REQUIRED ({unit.lane}) ***")
        print(f"  Gates passing is necessary, not sufficient. This shot plan is NOT "
              f"render-ready until a human has read it against the CSV and signed off.")

    print(f"\n  verdict: {'FAIL' if any_fail else 'PASS (gates clean; human sign-off still required)'}")
    return 1 if any_fail else 0


def cmd_plan(args) -> int:
    cfg = cfgmod.load()
    return validate_shotplan(cfg, args.unit)


def cmd_run(args) -> int:
    print(f"  TODO: render + brand gate + versioned draft write for "
          f"{args.unit or ('season ' + str(args.season))} — held for a follow-up pass")
    return 0


def cmd_drift(_args) -> int:
    print("  TODO Phase 6: compare stored csv_sha256 against current CSVs")
    return 0


def main() -> int:
    p = argparse.ArgumentParser(prog="produce")
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("doctor").set_defaults(fn=cmd_doctor)

    sp = sub.add_parser("plan");  sp.add_argument("--unit", required=True); sp.set_defaults(fn=cmd_plan)
    sr = sub.add_parser("run")
    sr.add_argument("--unit"); sr.add_argument("--season", type=int); sr.set_defaults(fn=cmd_run)
    sub.add_parser("drift").set_defaults(fn=cmd_drift)

    args = p.parse_args()
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd D:\System_Synthesis\06_Video_Production\FundaForge-Video-Renderer && python -m pytest tests/test_plan_validator.py -v`
Expected: all 3 tests PASS.

Then run the full suite to confirm nothing broke:

Run: `cd D:\System_Synthesis\06_Video_Production\FundaForge-Video-Renderer && python -m pytest tests/ -v`
Expected: all tests PASS (4 original fidelity + 3 new fidelity + 5 humanization + 3 plan validator = 15 total).

- [ ] **Step 5: Commit**

```bash
cd D:\System_Synthesis\06_Video_Production\FundaForge-Video-Renderer
git add produce.py tests/test_plan_validator.py
git commit -m "$(cat <<'EOF'
Rewire produce.py plan as a shot-plan validator, not a generator

Script generation moved out of this codebase (Claude drafts shot
plans interactively in Cowork chat now, per CLAUDE.md's updated
LOCKED DECISIONS). plan --unit <ID> now: requires an existing
out/shotplans/<ID>_shotplan.json (fails clearly if missing, never
generates one), validates it against the schema, runs the fidelity
gate (with the new fabrication check), the new humanization gate, and
the brand gate, and prints a combined report. Always prints the
human-script-review sign-off notice, now mandatory for both lanes.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 4: Hand-authored BP34 fixtures and end-to-end proof

**Files:**
- Create: `out/shotplans/BP34_shotplan_bad_example.json` (kept as a permanent regression fixture, NOT the live `BP34_shotplan.json` name — avoid colliding with a real future Cowork-authored plan for this unit)
- Create: `out/shotplans/BP34_shotplan_clean_example.json`

**Interfaces:**
- Consumes: `produce.py`'s `validate_shotplan()` via the actual CLI (`python produce.py plan --unit BP34`), which reads from `out/shotplans/<unit>_shotplan.json` by convention — for this manual end-to-end proof (as opposed to Task 3's automated tests, which already cover the logic via `tmp_path`), temporarily copy each fixture to `out/shotplans/BP34_shotplan.json`, run the CLI, and restore.

- [ ] **Step 1: Write the bad shot plan fixture**

Create `out/shotplans/BP34_shotplan_bad_example.json` — a full, schema-shaped shot plan (all required top-level fields: `unit_id`, `lane`, `kicker`, `accent`, `fps`, `width`, `height`, `duration_frames`, `audio`, `scenes`) covering BP34's real slide 1 (hook, verbatim), a flattened slide 4, a fabricated detail, a triplet, and "leveraging" — for example:

```json
{
  "unit_id": "BP34",
  "lane": "blueprint",
  "series": "Arc 3",
  "kicker": "BANKING-GRADE AI \u00b7 ARC 3 \u00b7 LINEAGE AND SOVEREIGNTY",
  "accent": "#F59E0B",
  "fps": 30,
  "width": 1080,
  "height": 1920,
  "duration_frames": 900,
  "audio": {
    "voice_file": null,
    "voice_id": "1aP69VftkGksPi01itpR",
    "model_id": "eleven_multilingual_v2",
    "music_file": "assets/music/blueprint_bed.mp3",
    "music_gain_db": -20
  },
  "scenes": [
    {
      "scene_id": 1,
      "card": "TitleCard",
      "start_frame": 0,
      "duration_frames": 150,
      "slide_refs": [1],
      "headline": "Delete me. The bank cannot.",
      "body": "A customer exercises erasure. A separate obligation requires the bank to keep transaction records for years. Both are law, and they point opposite ways."
    },
    {
      "scene_id": 2,
      "card": "BodyCard",
      "start_frame": 150,
      "duration_frames": 240,
      "slide_refs": [4],
      "headline": "Retention wins.",
      "body": "The bank must keep every record for exactly eleven years, leveraging a fast, reliable, and scalable archive to do it."
    },
    {
      "scene_id": 3,
      "card": "TrapCard",
      "start_frame": 390,
      "duration_frames": 330,
      "slide_refs": [9],
      "headline": "Reconcile erasure with seven-year retention.",
      "body": "Name which records are retained under which duty, what was deleted, and who approved the split. Answers claiming full erasure have not read the retention rules."
    },
    {
      "scene_id": 4,
      "card": "CTACard",
      "start_frame": 720,
      "duration_frames": 180,
      "slide_refs": [10],
      "headline": "Save this. It has no easy answer.",
      "body": "The hardest problem in this arc, and the one most likely to come up in a real assessment."
    }
  ],
  "cta": { "tier": 2, "on_screen": "FOLLOW FOR THE NEXT ONE", "next_unit": null }
}
```

- [ ] **Step 2: Write the clean shot plan fixture**

Create `out/shotplans/BP34_shotplan_clean_example.json` — same shape, but scene 2's text preserves the CSV's actual hedges verbatim and introduces no invented details, no banned words, no triplet:

```json
{
  "unit_id": "BP34",
  "lane": "blueprint",
  "series": "Arc 3",
  "kicker": "BANKING-GRADE AI \u00b7 ARC 3 \u00b7 LINEAGE AND SOVEREIGNTY",
  "accent": "#F59E0B",
  "fps": 30,
  "width": 1080,
  "height": 1920,
  "duration_frames": 900,
  "audio": {
    "voice_file": null,
    "voice_id": "1aP69VftkGksPi01itpR",
    "model_id": "eleven_multilingual_v2",
    "music_file": "assets/music/blueprint_bed.mp3",
    "music_gain_db": -20
  },
  "scenes": [
    {
      "scene_id": 1,
      "card": "TitleCard",
      "start_frame": 0,
      "duration_frames": 150,
      "slide_refs": [1],
      "headline": "Delete me. The bank cannot.",
      "body": "A customer exercises erasure. A separate obligation requires the bank to keep transaction records for years. Both are law, and they point opposite ways."
    },
    {
      "scene_id": 2,
      "card": "BodyCard",
      "start_frame": 150,
      "duration_frames": 240,
      "slide_refs": [4],
      "headline": "Retention usually wins, narrowly.",
      "body": "Where a statutory duty to retain exists, it generally overrides an erasure request for those specific records. The rest must still go."
    },
    {
      "scene_id": 3,
      "card": "TrapCard",
      "start_frame": 390,
      "duration_frames": 330,
      "slide_refs": [9],
      "headline": "Reconcile erasure with seven-year retention.",
      "body": "Name which records are retained under which duty, what was deleted, and who approved the split. Answers claiming full erasure have not read the retention rules."
    },
    {
      "scene_id": 4,
      "card": "CTACard",
      "start_frame": 720,
      "duration_frames": 180,
      "slide_refs": [10],
      "headline": "Save this. It has no easy answer.",
      "body": "The hardest problem in this arc, and the one most likely to come up in a real assessment."
    }
  ],
  "cta": { "tier": 2, "on_screen": "FOLLOW FOR THE NEXT ONE", "next_unit": null }
}
```

- [ ] **Step 3: Run the bad fixture through the real CLI**

```bash
cd D:\System_Synthesis\06_Video_Production\FundaForge-Video-Renderer
cp out/shotplans/BP34_shotplan_bad_example.json out/shotplans/BP34_shotplan.json
python produce.py plan --unit BP34
```

Expected output includes: `[FAIL] fidelity TRAP_FLATTENED` or `HEDGE_DROPPED` (scene 2 flattened "usually...narrowly...generally...those specific" into a flat rule), `[warn] fidelity POSSIBLE_FABRICATION` naming "eleven" or "eleven years" (the source only ever says "seven-year" on slide 9, in a different context — the CTA/trap slide, not slide 4 — so "eleven years" on slide 4 is a genuine invention), `[warn] humanization POSSIBLE_TRIPLET` and `[warn] humanization BANNED_PHRASE` naming "leveraging", the `HUMAN SCRIPT REVIEW REQUIRED (blueprint)` banner, and `verdict: FAIL`. Exit code should be 1 (`echo $?` after running, or check via `$LASTEXITCODE` if using PowerShell).

- [ ] **Step 4: Run the clean fixture through the real CLI**

```bash
cd D:\System_Synthesis\06_Video_Production\FundaForge-Video-Renderer
cp out/shotplans/BP34_shotplan_clean_example.json out/shotplans/BP34_shotplan.json
python produce.py plan --unit BP34
```

Expected output: `schema: valid`, a `WARN` line for `ig_status` (BP34 is `"not yet"` published — this should print but not affect the verdict), `fidelity: no findings`, `humanization: no findings`, `brand: no findings` (or only warns, no fails), the `HUMAN SCRIPT REVIEW REQUIRED` banner still printing (mandatory regardless of gate cleanliness), and `verdict: PASS (gates clean; human sign-off still required)`. Exit code 0.

- [ ] **Step 5: Remove the working copy, keep the named fixtures**

```bash
rm out/shotplans/BP34_shotplan.json
```

The two example fixtures (`BP34_shotplan_bad_example.json`, `BP34_shotplan_clean_example.json`) stay as permanent regression material; the working-copy `BP34_shotplan.json` is deliberately not committed, since that filename is reserved for a real future Cowork-authored plan.

- [ ] **Step 6: Commit the fixtures**

```bash
cd D:\System_Synthesis\06_Video_Production\FundaForge-Video-Renderer
git add out/shotplans/BP34_shotplan_bad_example.json out/shotplans/BP34_shotplan_clean_example.json
git status
```

Confirm `out/shotplans/BP34_shotplan.json` does NOT appear in `git status` (removed in Step 5, never committed). Then:

```bash
git commit -m "$(cat <<'EOF'
Add hand-authored BP34 shot-plan fixtures proving both gates work

bad_example flattens slide 4's hedge, invents an eleven-year
retention period the CSV never states, and carries a triplet plus
"leveraging" — confirmed to fail fidelity (flattening), warn on
fabrication, and warn on humanization when run through
produce.py plan. clean_example is faithful to the CSV and passes all
three with no findings. Manually verified via the real CLI, not just
the unit tests in Task 3.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

## Post-plan note

`render.py`, `tracker.py`, and the eventual removal of `script.py`/
`assets.py`/`shotlist.py` references from documentation that still mentions
them (e.g. the setup doc's repo-structure table, if it hasn't been updated
elsewhere) are explicitly out of scope here — held for a follow-up pass once
`plan`'s validator has a track record against real Cowork-authored shot
plans, not fixtures.
