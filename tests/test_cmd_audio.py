"""Tests for produce.py's `audio` command: apply_audio_result_to_shotplan,
run_audio_for_unit, and cmd_audio. pipeline.audio.synthesize_unit_audio is
monkeypatched throughout — its own correctness (offset math, caching,
pronunciation) is covered in tests/test_audio.py. What's under test here
is the orchestration: gate-before-spend, merging the result back into the
shot plan on disk, and the argparse-facing wrapper.
"""
import argparse
import json
from pathlib import Path

import produce


def _fake_result(unit_id="BP34"):
    return {
        "voice_file": f"out/audio/{unit_id}_voice.mp3",
        "voice_id": "v1",
        "model_id": "m1",
        "scenes": [{"scene_id": 1, "card": "TitleCard", "start_frame": 0,
                    "duration_frames": 90, "headline": "h", "body": "b"}],
        "captions": [{"text": "h", "start_frame": 0, "end_frame": 10}],
        "duration_frames": 90,
        "segments_synthesized": 1,
    }


def test_apply_audio_result_does_not_mutate_input():
    original = {"unit_id": "BP34", "audio": {"music_file": "assets/music/x.mp3"},
                "scenes": [{"scene_id": 1}], "duration_frames": 600}
    result = _fake_result()

    updated = produce.apply_audio_result_to_shotplan(original, result)

    assert original["scenes"] == [{"scene_id": 1}]  # untouched
    assert original["duration_frames"] == 600
    assert "voice_file" not in original["audio"]


def test_apply_audio_result_merges_audio_fields_and_preserves_music():
    original = {"unit_id": "BP34", "audio": {"music_file": "assets/music/blueprint_bed.mp3",
                                              "music_gain_db": -20},
                "scenes": [], "duration_frames": 0}
    result = _fake_result()

    updated = produce.apply_audio_result_to_shotplan(original, result)

    assert updated["audio"]["voice_file"] == "out/audio/BP34_voice.mp3"
    assert updated["audio"]["voice_id"] == "v1"
    assert updated["audio"]["model_id"] == "m1"
    # sync_music_asset still needs this — merging voice must not clobber it
    assert updated["audio"]["music_file"] == "assets/music/blueprint_bed.mp3"
    assert updated["scenes"] == result["scenes"]
    assert updated["captions"] == result["captions"]
    assert updated["duration_frames"] == 90


def test_run_audio_refuses_when_gates_fail(tmp_path, monkeypatch):
    monkeypatch.setattr(produce, "validate_shotplan", lambda cfg, unit_id, shotplans_dir=None: 1)
    called = {"synth": False}
    monkeypatch.setattr(produce.audiomod, "synthesize_unit_audio",
                         lambda *a, **kw: called.__setitem__("synth", True) or _fake_result())

    exit_code = produce.run_audio_for_unit(cfg=object(), unit_id="BP34", shotplans_dir=tmp_path)

    assert exit_code == 1
    assert called["synth"] is False


def test_run_audio_writes_updated_shotplan_on_success(tmp_path, monkeypatch, capsys):
    shotplans_dir = tmp_path
    plan = {"unit_id": "BP34", "fps": 30, "audio": {"music_file": "assets/music/x.mp3"},
            "scenes": [{"scene_id": 1}], "duration_frames": 600}
    plan_path = shotplans_dir / "BP34_shotplan.json"
    plan_path.write_text(json.dumps(plan), encoding="utf-8")

    monkeypatch.setattr(produce, "validate_shotplan", lambda cfg, unit_id, shotplans_dir=None: 0)
    monkeypatch.setattr(produce.audiomod, "synthesize_unit_audio",
                         lambda cfg, shotplan, force=False: _fake_result())

    exit_code = produce.run_audio_for_unit(cfg=object(), unit_id="BP34", shotplans_dir=shotplans_dir)

    assert exit_code == 0
    out = capsys.readouterr().out
    assert "1 scene(s) synthesized/cached" in out
    assert "Shot plan updated in place" in out

    updated = json.loads(plan_path.read_text(encoding="utf-8"))
    assert updated["audio"]["voice_file"] == "out/audio/BP34_voice.mp3"
    assert updated["audio"]["music_file"] == "assets/music/x.mp3"  # preserved
    assert updated["duration_frames"] == 90


def test_run_audio_reports_runtime_error_from_synthesis(tmp_path, monkeypatch, capsys):
    plan = {"unit_id": "BP34", "fps": 30, "audio": {}, "scenes": [], "duration_frames": 600}
    (tmp_path / "BP34_shotplan.json").write_text(json.dumps(plan), encoding="utf-8")

    monkeypatch.setattr(produce, "validate_shotplan", lambda cfg, unit_id, shotplans_dir=None: 0)

    def _raise(cfg, shotplan, force=False):
        raise RuntimeError("ELEVENLABS_API_KEY not set.")
    monkeypatch.setattr(produce.audiomod, "synthesize_unit_audio", _raise)

    exit_code = produce.run_audio_for_unit(cfg=object(), unit_id="BP34", shotplans_dir=tmp_path)

    assert exit_code == 1
    out = capsys.readouterr().out
    assert "ELEVENLABS_API_KEY" in out


def test_cmd_audio_requires_unit():
    args = argparse.Namespace(unit=None, force=False)
    assert produce.cmd_audio(args) == 1
