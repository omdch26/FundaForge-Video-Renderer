"""Tests for cmd_run's supporting functions in produce.py: asset syncing,
draft versioning, and the render-gate orchestration in run_unit.

These are hermetic — they monkeypatch produce.REPO_ROOT / produce.REMOTION_DIR
and the config/unit-loading calls rather than depending on the real
System_Synthesis tree, so they run the same in any sandbox. The one thing
genuinely impossible to test anywhere but Sri's own Windows machine is
whether `npx remotion render` itself succeeds (native rspack bindings are
platform-specific — confirmed 18 Aug 2026 in both this session's cloud
sandbox and the device bridge's Linux VM). render_unit is monkeypatched out
in every test here; it is never actually invoked.
"""
import json
from pathlib import Path

import pytest

import produce
from pipeline.source import Unit


class FakeConfig:
    """Minimal stand-in for pipeline.config.Config — just enough surface for
    sync_diagram_assets / sync_music_asset / run_unit to work against,
    without needing a real SYSTEM_ROOT or lanes.yaml on disk."""

    def __init__(self, vector_library: Path, lanes: dict):
        self._vector_library = vector_library
        self._lanes = lanes

    def ro(self, key):
        assert key == "vector_library"
        return self._vector_library

    def lane(self, name):
        return self._lanes[name]


def _fake_unit(lane="blueprint"):
    return Unit(
        unit_id="BP34", lane=lane, series="B", tier="1", kicker="K",
        hook_slide1="h", why_slide2="w", cta_type="plain", keyword=None,
        ig_status="published", csv_path="x.csv",
    )


# ---------------------------------------------------------------------------
# sync_diagram_assets
# ---------------------------------------------------------------------------

def test_sync_diagram_assets_copies_from_vector_library(tmp_path, monkeypatch):
    vector_lib = tmp_path / "vector_library"
    (vector_lib / "T1_Core_Concepts").mkdir(parents=True)
    svg = vector_lib / "T1_Core_Concepts" / "Drift_Types_Three.svg"
    svg.write_text("<svg/>", encoding="utf-8")

    remotion_dir = tmp_path / "remotion"
    monkeypatch.setattr(produce, "REMOTION_DIR", remotion_dir)

    cfg = FakeConfig(vector_lib, {})
    shotplan = {"scenes": [
        {"asset": {"kind": "svg_library", "path": "diagrams/Drift_Types_Three.svg"}},
    ]}

    synced = produce.sync_diagram_assets(cfg, shotplan)

    assert synced == ["Drift_Types_Three.svg"]
    dest = remotion_dir / "public" / "diagrams" / "Drift_Types_Three.svg"
    assert dest.exists()
    assert dest.read_text(encoding="utf-8") == "<svg/>"


def test_sync_diagram_assets_skips_already_present(tmp_path, monkeypatch):
    vector_lib = tmp_path / "vector_library"  # deliberately has nothing to find
    vector_lib.mkdir()
    remotion_dir = tmp_path / "remotion"
    dest_dir = remotion_dir / "public" / "diagrams"
    dest_dir.mkdir(parents=True)
    (dest_dir / "Already_There.svg").write_text("<svg>existing</svg>", encoding="utf-8")
    monkeypatch.setattr(produce, "REMOTION_DIR", remotion_dir)

    cfg = FakeConfig(vector_lib, {})
    shotplan = {"scenes": [
        {"asset": {"kind": "svg_library", "path": "diagrams/Already_There.svg"}},
    ]}

    synced = produce.sync_diagram_assets(cfg, shotplan)

    assert synced == ["Already_There.svg"]
    # untouched — proves it was recognised as already-present, not re-copied
    assert (dest_dir / "Already_There.svg").read_text(encoding="utf-8") == "<svg>existing</svg>"


def test_sync_diagram_assets_missing_raises(tmp_path, monkeypatch):
    vector_lib = tmp_path / "vector_library"
    vector_lib.mkdir()
    remotion_dir = tmp_path / "remotion"
    monkeypatch.setattr(produce, "REMOTION_DIR", remotion_dir)

    cfg = FakeConfig(vector_lib, {})
    shotplan = {"scenes": [
        {"asset": {"kind": "svg_library", "path": "diagrams/Does_Not_Exist.svg"}},
    ]}

    with pytest.raises(FileNotFoundError, match="Does_Not_Exist.svg"):
        produce.sync_diagram_assets(cfg, shotplan)


def test_sync_diagram_assets_ignores_non_library_assets(tmp_path, monkeypatch):
    """manual_drop / svg_local assets are placed by hand, not synced from the
    vector library — sync_diagram_assets must leave them alone, and a scene
    with no asset at all must not blow up."""
    vector_lib = tmp_path / "vector_library"
    vector_lib.mkdir()
    remotion_dir = tmp_path / "remotion"
    monkeypatch.setattr(produce, "REMOTION_DIR", remotion_dir)

    cfg = FakeConfig(vector_lib, {})
    shotplan = {"scenes": [
        {"asset": {"kind": "manual_drop", "path": "diagrams/Hand_Made.svg"}},
        {"card": "BodyCard"},
    ]}

    synced = produce.sync_diagram_assets(cfg, shotplan)
    assert synced == []


# ---------------------------------------------------------------------------
# sync_music_asset
# ---------------------------------------------------------------------------

def test_sync_music_asset_copies(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    (repo_root / "assets" / "music").mkdir(parents=True)
    src = repo_root / "assets" / "music" / "blueprint_bed.mp3"
    src.write_bytes(b"fake-mp3-bytes")
    remotion_dir = repo_root / "remotion"
    monkeypatch.setattr(produce, "REPO_ROOT", repo_root)
    monkeypatch.setattr(produce, "REMOTION_DIR", remotion_dir)

    shotplan = {"audio": {"music_file": "assets/music/blueprint_bed.mp3"}}
    result = produce.sync_music_asset(None, shotplan)

    assert result == "assets/music/blueprint_bed.mp3"
    dest = remotion_dir / "public" / "assets" / "music" / "blueprint_bed.mp3"
    assert dest.exists()
    assert dest.read_bytes() == b"fake-mp3-bytes"


def test_sync_music_asset_none_referenced_returns_none(tmp_path, monkeypatch):
    monkeypatch.setattr(produce, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(produce, "REMOTION_DIR", tmp_path / "remotion")
    assert produce.sync_music_asset(None, {"audio": {}}) is None
    assert produce.sync_music_asset(None, {}) is None


def test_sync_music_asset_missing_source_raises(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    monkeypatch.setattr(produce, "REPO_ROOT", repo_root)
    monkeypatch.setattr(produce, "REMOTION_DIR", repo_root / "remotion")

    shotplan = {"audio": {"music_file": "assets/music/nope.mp3"}}
    with pytest.raises(FileNotFoundError, match="nope.mp3"):
        produce.sync_music_asset(None, shotplan)


# ---------------------------------------------------------------------------
# next_draft_version
# ---------------------------------------------------------------------------

def test_next_draft_version_empty_dir_returns_1(tmp_path, monkeypatch):
    monkeypatch.setattr(produce, "REPO_ROOT", tmp_path)
    assert produce.next_draft_version("BP34") == 1


def test_next_draft_version_returns_max_plus_1(tmp_path, monkeypatch):
    monkeypatch.setattr(produce, "REPO_ROOT", tmp_path)
    drafts_dir = tmp_path / "out" / "drafts" / "BP34"
    drafts_dir.mkdir(parents=True)
    (drafts_dir / "BP34_v1.mp4").touch()
    (drafts_dir / "BP34_v3.mp4").touch()  # gap — an earlier draft was removed by hand
    (drafts_dir / "BP34_v2.mp4").touch()
    assert produce.next_draft_version("BP34") == 4


# ---------------------------------------------------------------------------
# run_unit — the gate/orchestration logic, with render_unit mocked out.
# ---------------------------------------------------------------------------

def test_run_unit_refuses_when_gates_fail(tmp_path, monkeypatch):
    monkeypatch.setattr(produce, "validate_shotplan", lambda cfg, unit_id, shotplans_dir=None: 1)
    called = {"render": False}
    monkeypatch.setattr(produce, "render_unit",
                         lambda *a, **kw: called.__setitem__("render", True) or Path("x"))

    exit_code = produce.run_unit(FakeConfig(tmp_path, {}), "BP34", confirmed=True, shotplans_dir=tmp_path)

    assert exit_code == 1
    assert called["render"] is False


def test_run_unit_refuses_without_confirmation_for_human_review_lane(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(produce, "validate_shotplan", lambda cfg, unit_id, shotplans_dir=None: 0)
    monkeypatch.setattr(produce.source, "load_unit", lambda cfg, unit_id: _fake_unit(lane="blueprint"))
    called = {"render": False}
    monkeypatch.setattr(produce, "render_unit",
                         lambda *a, **kw: called.__setitem__("render", True) or Path("x"))

    cfg = FakeConfig(tmp_path, {"blueprint": {"human_script_review": True}})
    exit_code = produce.run_unit(cfg, "BP34", confirmed=False, shotplans_dir=tmp_path)

    assert exit_code == 1
    assert called["render"] is False
    out = capsys.readouterr().out
    assert "--confirmed" in out


def test_run_unit_refuses_without_synthesized_audio(tmp_path, monkeypatch, capsys):
    """New behaviour: a shot plan whose scene timings/captions still come
    from the authored guess (no Phase 3 audio.voice_file yet) must not be
    rendered — `produce.py audio` has to run first."""
    shotplans_dir = tmp_path / "shotplans"
    shotplans_dir.mkdir()
    plan = {"unit_id": "BP34", "audio": {}, "scenes": []}  # no voice_file
    (shotplans_dir / "BP34_shotplan.json").write_text(json.dumps(plan), encoding="utf-8")

    monkeypatch.setattr(produce, "validate_shotplan", lambda cfg, unit_id, shotplans_dir=None: 0)
    monkeypatch.setattr(produce.source, "load_unit", lambda cfg, unit_id: _fake_unit(lane="season"))
    called = {"render": False}
    monkeypatch.setattr(produce, "render_unit",
                         lambda *a, **kw: called.__setitem__("render", True) or Path("x"))

    cfg = FakeConfig(tmp_path, {"season": {"human_script_review": False}})
    exit_code = produce.run_unit(cfg, "BP34", confirmed=False, shotplans_dir=shotplans_dir)

    assert exit_code == 1
    assert called["render"] is False
    out = capsys.readouterr().out
    assert "produce.py audio --unit BP34" in out


def test_run_unit_success_path(tmp_path, monkeypatch, capsys):
    shotplans_dir = tmp_path / "shotplans"
    shotplans_dir.mkdir()
    plan = {"unit_id": "BP34", "audio": {"voice_file": "out/audio/BP34_voice.mp3"}, "scenes": []}
    (shotplans_dir / "BP34_shotplan.json").write_text(json.dumps(plan), encoding="utf-8")

    monkeypatch.setattr(produce, "validate_shotplan", lambda cfg, unit_id, shotplans_dir=None: 0)
    monkeypatch.setattr(produce.source, "load_unit", lambda cfg, unit_id: _fake_unit(lane="season"))
    monkeypatch.setattr(produce, "sync_diagram_assets", lambda cfg, sp: [])
    monkeypatch.setattr(produce, "sync_music_asset", lambda cfg, sp: None)
    monkeypatch.setattr(produce, "sync_voice_asset", lambda sp: "out/audio/BP34_voice.mp3")

    fake_output = tmp_path / "out" / "drafts" / "BP34" / "BP34_v1.mp4"
    monkeypatch.setattr(produce, "render_unit", lambda unit_id, shotplan_path: fake_output)

    cfg = FakeConfig(tmp_path, {"season": {"human_script_review": False}})
    exit_code = produce.run_unit(cfg, "BP34", confirmed=False, shotplans_dir=shotplans_dir)

    assert exit_code == 0
    out = capsys.readouterr().out
    assert "Draft written" in out
    assert str(fake_output) in out
    assert "not an approved final" in out


def test_run_unit_asset_sync_failure_stops_before_render(tmp_path, monkeypatch):
    shotplans_dir = tmp_path / "shotplans"
    shotplans_dir.mkdir()
    plan = {"unit_id": "BP34", "audio": {"voice_file": "out/audio/BP34_voice.mp3"}, "scenes": []}
    (shotplans_dir / "BP34_shotplan.json").write_text(json.dumps(plan), encoding="utf-8")

    monkeypatch.setattr(produce, "validate_shotplan", lambda cfg, unit_id, shotplans_dir=None: 0)
    monkeypatch.setattr(produce.source, "load_unit", lambda cfg, unit_id: _fake_unit(lane="season"))

    def _raise(cfg, sp):
        raise FileNotFoundError("missing diagram")
    monkeypatch.setattr(produce, "sync_diagram_assets", _raise)

    called = {"render": False}
    monkeypatch.setattr(produce, "render_unit",
                         lambda *a, **kw: called.__setitem__("render", True) or Path("x"))

    cfg = FakeConfig(tmp_path, {"season": {"human_script_review": False}})
    exit_code = produce.run_unit(cfg, "BP34", confirmed=False, shotplans_dir=shotplans_dir)

    assert exit_code == 1
    assert called["render"] is False


# ---------------------------------------------------------------------------
# cmd_run — the argparse-facing wrapper
# ---------------------------------------------------------------------------

def test_cmd_run_requires_unit_when_no_season(monkeypatch):
    args = argparse_namespace(unit=None, season=None, confirmed=False)
    assert produce.cmd_run(args) == 1


def test_cmd_run_season_batch_not_implemented(monkeypatch):
    args = argparse_namespace(unit=None, season=1, confirmed=False)
    assert produce.cmd_run(args) == 1


def argparse_namespace(**kwargs):
    import argparse
    return argparse.Namespace(**kwargs)
