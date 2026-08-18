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
    items = list(headline_body_by_scene.items())
    for i, (scene_id, (headline, body)) in enumerate(items):
        # Schema requires duration_frames total >= 600; pad the last scene
        # so 3 test scenes at 150 frames each (450 total) still validates.
        duration = 150 if i < len(items) - 1 else 300
        scenes.append({
            "scene_id": scene_id,
            "card": "BodyCard" if scene_id not in (1, 9) else ("TitleCard" if scene_id == 1 else "TrapCard"),
            "start_frame": frame,
            "duration_frames": duration,
            "slide_refs": slide_refs_by_scene[scene_id],
            "headline": headline,
            "body": body,
        })
        frame += duration
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


FIXTURES_DIR = Path(__file__).parent / "fixtures"


def test_full_bad_fixture_catches_hedge_dropped_per_slide(tmp_path, capsys):
    """Regression test, added 18 Aug 2026.

    The committed tests/fixtures/BP34_shotplan_bad_example.json fixture only
    flattens slide 4 ("Retention wins." for "Retention usually wins,
    narrowly...") — every other scene is otherwise faithful, and several
    (slides 2, 5, 8, 10) legitimately use words that ARE in HEDGE_MARKERS
    ("no clean resolution", "partial", "no easy answer"). Proven empirically
    on 18 Aug 2026: under the old whole-script HEDGE_DROPPED check, those
    other scenes' hedge language satisfied the check, so slide 4's flattening
    went completely uncaught and the fixture passed the entire gate suite —
    exit_code 0 — despite being the exact failure mode this gate exists to
    prevent. This test is the permanent proof that regression doesn't happen
    again; if it ever goes green without HEDGE_DROPPED specifically present,
    the per-slide fix has been undone.
    """
    fixture = json.loads((FIXTURES_DIR / "BP34_shotplan_bad_example.json").read_text(encoding="utf-8"))
    (tmp_path / "BP34_shotplan.json").write_text(json.dumps(fixture), encoding="utf-8")

    cfg = cfgmod.load()
    exit_code = produce.validate_shotplan(cfg, "BP34", shotplans_dir=tmp_path)

    out = capsys.readouterr().out
    assert exit_code != 0
    assert "HEDGE_DROPPED" in out
    assert "Slide 4" in out  # the specific slide, not a whole-script proxy
    assert "POSSIBLE_FABRICATION" in out
    assert "eleven years" in out
    assert "leveraging" in out.lower()


def test_full_clean_fixture_passes_cleanly(tmp_path, capsys):
    """Companion to the above — the committed clean fixture, same 10-slide
    shape, faithful throughout, must pass with zero fail-severity findings."""
    fixture = json.loads((FIXTURES_DIR / "BP34_shotplan_clean_example.json").read_text(encoding="utf-8"))
    (tmp_path / "BP34_shotplan.json").write_text(json.dumps(fixture), encoding="utf-8")

    cfg = cfgmod.load()
    exit_code = produce.validate_shotplan(cfg, "BP34", shotplans_dir=tmp_path)

    out = capsys.readouterr().out
    assert exit_code == 0
    assert "HEDGE_DROPPED" not in out
    assert "TRAP_FLATTENED" not in out
