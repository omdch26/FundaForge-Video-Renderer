"""Tests for pipeline/gates/audio_gate.py — G3: words-per-second, voice/
model identity, and best-effort clipping detection.
"""
import pytest

from pipeline.gates import audio_gate


class _FakeConfig:
    def __init__(self, lanes, pipeline=None):
        self._lanes = lanes
        self.pipeline = pipeline or {"audio": {"target_wps": [2.2, 2.8], "peak_ceiling_db": -1.0}}

    def lane(self, name):
        return self._lanes[name]


def _plan(words_per_scene, duration_frames, fps=30, voice_id=None, model_id=None):
    scenes = []
    for i, n_words in enumerate(words_per_scene, start=1):
        text = " ".join(f"w{i}_{j}" for j in range(n_words))
        scenes.append({"scene_id": i, "card": "BodyCard", "headline": text, "body": ""})
    return {
        "lane": "season", "fps": fps, "duration_frames": duration_frames,
        "audio": {"voice_id": voice_id, "model_id": model_id},
        "scenes": scenes,
    }


def test_wps_in_range_no_finding():
    # 60 words over 20s = 3.0 wps... let's target inside [2.2, 2.8]: 50 words / 20s = 2.5
    plan = _plan([50], duration_frames=600, fps=30)  # 20s
    cfg = _FakeConfig({"season": {"voice_id": None, "model_id": None}})
    findings = audio_gate.check(cfg, None, plan)
    assert not any(f.code == "WPS_OUT_OF_RANGE" for f in findings)


def test_wps_too_fast_warns():
    plan = _plan([100], duration_frames=600, fps=30)  # 100 words / 20s = 5.0 wps
    cfg = _FakeConfig({"season": {"voice_id": None, "model_id": None}})
    findings = audio_gate.check(cfg, None, plan)
    hits = [f for f in findings if f.code == "WPS_OUT_OF_RANGE"]
    assert len(hits) == 1
    assert hits[0].severity == "warn"
    assert "rushed" in hits[0].message.lower()


def test_wps_too_slow_warns():
    plan = _plan([10], duration_frames=600, fps=30)  # 10 words / 20s = 0.5 wps
    cfg = _FakeConfig({"season": {"voice_id": None, "model_id": None}})
    findings = audio_gate.check(cfg, None, plan)
    hits = [f for f in findings if f.code == "WPS_OUT_OF_RANGE"]
    assert len(hits) == 1
    assert "draggy" in hits[0].message.lower()


def test_voice_id_mismatch_is_a_hard_fail():
    plan = _plan([50], duration_frames=600, voice_id="WRONG_ID", model_id="eleven_multilingual_v2")
    cfg = _FakeConfig({"season": {"voice_id": "Qc0h5B5Mqs8oaH4sFZ9X", "model_id": "eleven_multilingual_v2"}})
    findings = audio_gate.check(cfg, None, plan)
    hits = [f for f in findings if f.code == "VOICE_ID_MISMATCH"]
    assert len(hits) == 1
    assert hits[0].severity == "fail"
    assert not audio_gate.passed(findings)


def test_model_id_mismatch_is_a_hard_fail():
    plan = _plan([50], duration_frames=600, voice_id="Qc0h5B5Mqs8oaH4sFZ9X", model_id="eleven_turbo_v2")
    cfg = _FakeConfig({"season": {"voice_id": "Qc0h5B5Mqs8oaH4sFZ9X", "model_id": "eleven_multilingual_v2"}})
    findings = audio_gate.check(cfg, None, plan)
    hits = [f for f in findings if f.code == "MODEL_ID_MISMATCH"]
    assert len(hits) == 1
    assert hits[0].severity == "fail"


def test_matching_ids_no_finding():
    plan = _plan([50], duration_frames=600, voice_id="Qc0h5B5Mqs8oaH4sFZ9X", model_id="eleven_multilingual_v2")
    cfg = _FakeConfig({"season": {"voice_id": "Qc0h5B5Mqs8oaH4sFZ9X", "model_id": "eleven_multilingual_v2"}})
    findings = audio_gate.check(cfg, None, plan)
    assert not any(f.code in ("VOICE_ID_MISMATCH", "MODEL_ID_MISMATCH") for f in findings)


def test_absent_ids_not_checked():
    # Pre-synthesis shot plans may not stamp voice_id/model_id at all — that's
    # not this gate's business to enforce, only to catch when they DISAGREE.
    plan = _plan([50], duration_frames=600, voice_id=None, model_id=None)
    cfg = _FakeConfig({"season": {"voice_id": "Qc0h5B5Mqs8oaH4sFZ9X", "model_id": "eleven_multilingual_v2"}})
    findings = audio_gate.check(cfg, None, plan)
    assert not any(f.code in ("VOICE_ID_MISMATCH", "MODEL_ID_MISMATCH") for f in findings)


def test_clipping_not_checked_without_path():
    plan = _plan([50], duration_frames=600)
    cfg = _FakeConfig({"season": {"voice_id": None, "model_id": None}})
    findings = audio_gate.check(cfg, None, plan, voice_file_abspath=None)
    assert not any(f.code.startswith("AUDIO_NOT_SYNTHESIZED") or f.code == "CLIPPING" for f in findings)


def test_clipping_warns_when_file_missing(tmp_path):
    plan = _plan([50], duration_frames=600)
    cfg = _FakeConfig({"season": {"voice_id": None, "model_id": None}})
    missing = tmp_path / "does_not_exist.mp3"
    findings = audio_gate.check(cfg, None, plan, voice_file_abspath=missing)
    hits = [f for f in findings if f.code == "AUDIO_NOT_SYNTHESIZED"]
    assert len(hits) == 1
    assert hits[0].severity == "warn"


def test_passed_ignores_warnings():
    from pipeline.gates.audio_gate import Finding
    findings = [Finding("warn", "WPS_OUT_OF_RANGE", "x"), Finding("warn", "AUDIO_NOT_SYNTHESIZED", "y")]
    assert audio_gate.passed(findings) is True


def test_passed_false_on_any_fail():
    from pipeline.gates.audio_gate import Finding
    findings = [Finding("warn", "WPS_OUT_OF_RANGE", "x"), Finding("fail", "VOICE_ID_MISMATCH", "y")]
    assert audio_gate.passed(findings) is False


# --- clipping detection against a real (tiny) audio file -------------------

pytest.importorskip("pydub")
import shutil as _shutil  # noqa: E402
_HAVE_FFMPEG = _shutil.which("ffmpeg") is not None


@pytest.mark.skipif(not _HAVE_FFMPEG, reason="needs ffmpeg on PATH")
def test_clipping_fail_on_loud_clip(tmp_path):
    from pydub import AudioSegment
    from pydub.generators import Sine

    loud = Sine(440).to_audio_segment(duration=500).apply_gain(20)  # deliberately way over 0dBFS
    path = tmp_path / "loud.mp3"
    loud.export(path, format="mp3")

    plan = _plan([50], duration_frames=600)
    cfg = _FakeConfig({"season": {"voice_id": None, "model_id": None}})
    findings = audio_gate.check(cfg, None, plan, voice_file_abspath=path)
    assert any(f.code == "CLIPPING" and f.severity == "fail" for f in findings)


@pytest.mark.skipif(not _HAVE_FFMPEG, reason="needs ffmpeg on PATH")
def test_clipping_no_finding_on_quiet_clip(tmp_path):
    from pydub import AudioSegment
    from pydub.generators import Sine

    quiet = Sine(440).to_audio_segment(duration=500).apply_gain(-30)
    path = tmp_path / "quiet.mp3"
    quiet.export(path, format="mp3")

    plan = _plan([50], duration_frames=600)
    cfg = _FakeConfig({"season": {"voice_id": None, "model_id": None}})
    findings = audio_gate.check(cfg, None, plan, voice_file_abspath=path)
    assert not any(f.code == "CLIPPING" for f in findings)
