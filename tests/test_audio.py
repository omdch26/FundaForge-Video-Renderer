"""Tests for pipeline/audio.py — Phase 3: pronunciation, narration
segmentation, character-to-word timing, amber-to-caption-emphasis mapping,
per-scene caching, and scene retiming from actual speech length.

No real ElevenLabs calls anywhere in this file — synthesize_segment is
exercised against a fake client whose convert_with_timestamps returns
synthetic alignment data shaped exactly like the SDK's
AudioWithTimestampsResponse. That's what makes these hermetic: they prove
the OFFSET MATH and CACHING logic are correct without spending a credit or
needing network access, which this sandbox doesn't have anyway (same
reasoning as render_unit in tests/test_cmd_run.py).
"""
import json
import types

import pytest

from pipeline import audio


# ---------------------------------------------------------------------------
# apply_pronunciation
# ---------------------------------------------------------------------------

PRONUNCIATION = {
    "spell_out": ["GDPR", "API", "AI"],
    "replace": {"PyTorch": "pie-torch", "scikit-learn": "sy-kit learn"},
}


def test_apply_pronunciation_spells_out_acronyms():
    out = audio.apply_pronunciation("Under GDPR, this is required.", PRONUNCIATION)
    assert "G.D.P.R." in out
    assert "GDPR" not in out


def test_apply_pronunciation_preserves_word_count():
    text = "Under GDPR, this is required by the API."
    out = audio.apply_pronunciation(text, PRONUNCIATION)
    assert len(out.split()) == len(text.split())


def test_apply_pronunciation_replace_is_literal():
    out = audio.apply_pronunciation("We used PyTorch for this.", PRONUNCIATION)
    assert "pie-torch" in out
    assert "PyTorch" not in out


def test_apply_pronunciation_leaves_lowercase_acronym_like_words_alone():
    # "api" lowercase in prose should not be mistaken for the acronym "API"
    out = audio.apply_pronunciation("Design the api surface carefully.", PRONUNCIATION)
    assert "api" in out
    assert "A.P.I." not in out


def test_apply_pronunciation_keeps_trailing_punctuation():
    out = audio.apply_pronunciation("Required under GDPR.", PRONUNCIATION)
    assert out.endswith(".")


# ---------------------------------------------------------------------------
# narration segments
# ---------------------------------------------------------------------------

def _plan(scenes, cta=None):
    return {"unit_id": "T1", "lane": "season", "fps": 30, "scenes": scenes, "cta": cta}


def test_build_narration_segments_joins_headline_and_body():
    plan = _plan([{"scene_id": 1, "card": "TitleCard", "headline": "Hook.", "body": "More."}])
    segs = audio.build_narration_segments(plan, {"spell_out": [], "replace": {}})
    assert len(segs) == 1
    assert segs[0].raw_text == "Hook. More."


def test_build_narration_segments_skips_silent_scenes():
    plan = _plan([
        {"scene_id": 1, "card": "TitleCard", "headline": "Hook.", "body": "More."},
        {"scene_id": 2, "card": "DiagramCard", "asset": {"kind": "svg_library", "path": "x.svg"}},
    ])
    segs = audio.build_narration_segments(plan, {"spell_out": [], "replace": {}})
    assert [s.scene_id for s in segs] == [1]


def test_build_narration_segments_cta_scene_uses_spoken_override():
    plan = _plan(
        [{"scene_id": 3, "card": "CTACard", "headline": "On-screen only.", "body": ""}],
        cta={"tier": 1, "spoken": "Follow for the next one.", "on_screen": "FOLLOW"},
    )
    segs = audio.build_narration_segments(plan, {"spell_out": [], "replace": {}})
    assert segs[0].raw_text == "Follow for the next one."


def test_build_narration_segments_cta_scene_falls_back_to_headline_body():
    plan = _plan(
        [{"scene_id": 3, "card": "CTACard", "headline": "Next up.", "body": ""}],
        cta={"tier": 2, "on_screen": "SEE DESCRIPTION"},  # no "spoken"
    )
    segs = audio.build_narration_segments(plan, {"spell_out": [], "replace": {}})
    assert segs[0].raw_text == "Next up."


# ---------------------------------------------------------------------------
# word timing from character alignment
# ---------------------------------------------------------------------------

def _flat_alignment(text: str, ms_per_char: int = 50):
    """Synthetic alignment: every character takes ms_per_char, back to back —
    good enough to prove the offset math, not meant to look like real speech."""
    chars = list(text)
    starts = [i * ms_per_char for i in range(len(chars))]
    durations = [ms_per_char] * len(chars)
    return {"chars": chars, "char_start_times_ms": starts, "char_durations_ms": durations}


def test_word_times_ms_matches_word_boundaries():
    text = "Delete me now"
    alignment = _flat_alignment(text)
    times = audio._word_times_ms(alignment, text)
    assert len(times) == 3
    # "Delete" = chars 0-5, at 50ms/char: start 0, end (5+1)*50=300
    assert times[0] == (0, 300)


def test_word_times_ms_raises_on_length_mismatch():
    alignment = _flat_alignment("short")
    with pytest.raises(RuntimeError, match="alignment"):
        audio._word_times_ms(alignment, "a totally different, longer text")


# ---------------------------------------------------------------------------
# amber-span -> caption emphasis mapping
# ---------------------------------------------------------------------------

def test_scene_word_origins_tags_field_and_offsets():
    scene = {"headline": "Safe?", "body": "Not if you tuned it."}
    origins = audio._scene_word_origins(scene, cta=None)
    texts = [o["text"] for o in origins]
    assert texts == ["Safe?", "Not", "if", "you", "tuned", "it."]
    assert origins[0]["field"] == "headline"
    assert origins[1]["field"] == "body"


def test_word_is_amber_detects_overlap():
    amber_spans = [{"field": "body", "start": 0, "end": 8, "reason": "trap"}]
    word = {"field": "body", "start": 0, "end": 3}  # "Not"
    assert audio._word_is_amber(word, amber_spans) is True


def test_word_is_amber_false_outside_span():
    amber_spans = [{"field": "body", "start": 0, "end": 8, "reason": "trap"}]
    word = {"field": "body", "start": 20, "end": 24}
    assert audio._word_is_amber(word, amber_spans) is False


def test_word_is_amber_false_for_cta_words():
    # cta.spoken words carry field=None — amber_spans never apply to them
    word = {"field": None, "start": None, "end": None}
    assert audio._word_is_amber(word, [{"field": "body", "start": 0, "end": 100, "reason": "trap"}]) is False


def test_build_captions_marks_amber_words_constraint():
    plan = {
        "fps": 30,
        "cta": None,
        "scenes": [{
            "scene_id": 9, "card": "TrapCard",
            "headline": "Safe?",
            "body": "Not if you tuned it fifty times.",
            "amber_spans": [{"field": "body", "start": 0, "end": 3, "reason": "trap"}],  # "Not"
        }],
    }
    text = "Safe? Not if you tuned it fifty times."
    alignment = _flat_alignment(text)
    timeline = {9: (alignment, 0, len(text) * 50)}

    captions = audio.build_captions(plan, timeline)
    by_text = {c["text"]: c for c in captions}
    assert by_text["Not"].get("emphasis") == "constraint"
    assert "emphasis" not in by_text["Safe?"]


def test_build_captions_carries_amber_span_reason():
    # pipeline/gates/brand.py's AMBER_CAPTION_UNJUSTIFIED check wants a
    # caption's own `reason` field, not just emphasis="constraint" — this
    # was missing until caught by a real S1E05 run against pipeline/gates/brand.py.
    plan = {
        "fps": 30,
        "cta": None,
        "scenes": [{
            "scene_id": 9, "card": "TrapCard",
            "headline": "Safe?",
            "body": "Not if you tuned it fifty times.",
            "amber_spans": [{"field": "body", "start": 0, "end": 3, "reason": "trap"}],  # "Not"
        }],
    }
    text = "Safe? Not if you tuned it fifty times."
    alignment = _flat_alignment(text)
    timeline = {9: (alignment, 0, len(text) * 50)}

    captions = audio.build_captions(plan, timeline)
    by_text = {c["text"]: c for c in captions}
    assert by_text["Not"]["reason"] == "trap"
    assert "reason" not in by_text["Safe?"]


def test_build_captions_offsets_by_segment_start_ms():
    plan = {
        "fps": 30, "cta": None,
        "scenes": [{"scene_id": 1, "card": "TitleCard", "headline": "Hi", "body": ""}],
    }
    text = "Hi"
    alignment = _flat_alignment(text)
    # This scene's clip starts 1000ms into the assembled voice.mp3
    timeline = {1: (alignment, 1000, 1100)}
    captions = audio.build_captions(plan, timeline)
    assert captions[0]["start_frame"] == round(1000 / 1000 * 30)  # 30


# ---------------------------------------------------------------------------
# synthesize_segment — caching
# ---------------------------------------------------------------------------

class _FakeAlignment:
    """Mirrors the REAL elevenlabs SDK's CharacterAlignmentResponseModel
    shape (characters / character_start_times_seconds /
    character_end_times_seconds — seconds, start+end), not the ms/duration
    shape pipeline.audio converts into internally. See the conversion note
    in pipeline/audio.py::synthesize_segment for why these differ."""
    def __init__(self, chars, starts_ms, durations_ms):
        self.characters = chars
        self.character_start_times_seconds = [s / 1000 for s in starts_ms]
        self.character_end_times_seconds = [(s + d) / 1000 for s, d in zip(starts_ms, durations_ms)]


class _FakeResponse:
    def __init__(self, text, audio_b64):
        import base64
        alignment = _flat_alignment(text)
        self.audio_base_64 = base64.b64encode(audio_b64).decode("ascii")
        self.alignment = _FakeAlignment(
            alignment["chars"], alignment["char_start_times_ms"], alignment["char_durations_ms"])


class _FakeClient:
    def __init__(self):
        self.calls = []
        self.text_to_speech = types.SimpleNamespace(convert_with_timestamps=self._convert)

    def _convert(self, voice_id, *, text, model_id, output_format, previous_text, next_text):
        self.calls.append({"voice_id": voice_id, "text": text, "model_id": model_id})
        return _FakeResponse(text, b"FAKE-MP3-BYTES-" + text.encode("utf-8")[:4])


def test_synthesize_segment_calls_api_on_first_run(tmp_path):
    client = _FakeClient()
    seg = audio.NarrationSegment(scene_id=1, raw_text="Hi", tts_text="Hi")
    audio_bytes, alignment = audio.synthesize_segment(
        client, seg, "voice1", "model1",
        previous_text=None, next_text=None, cache_dir=tmp_path, unit_id="T1",
    )
    assert len(client.calls) == 1
    assert audio_bytes.startswith(b"FAKE-MP3")
    assert alignment["chars"] == ["H", "i"]


def test_synthesize_segment_uses_cache_on_second_run(tmp_path):
    client = _FakeClient()
    seg = audio.NarrationSegment(scene_id=1, raw_text="Hi", tts_text="Hi")
    audio.synthesize_segment(client, seg, "voice1", "model1",
                              previous_text=None, next_text=None,
                              cache_dir=tmp_path, unit_id="T1")
    audio.synthesize_segment(client, seg, "voice1", "model1",
                              previous_text=None, next_text=None,
                              cache_dir=tmp_path, unit_id="T1")
    assert len(client.calls) == 1  # second call served from cache


def test_synthesize_segment_recalls_api_when_text_changes(tmp_path):
    client = _FakeClient()
    seg1 = audio.NarrationSegment(scene_id=1, raw_text="Hi", tts_text="Hi")
    seg2 = audio.NarrationSegment(scene_id=1, raw_text="Hi there", tts_text="Hi there")
    audio.synthesize_segment(client, seg1, "voice1", "model1",
                              previous_text=None, next_text=None,
                              cache_dir=tmp_path, unit_id="T1")
    audio.synthesize_segment(client, seg2, "voice1", "model1",
                              previous_text=None, next_text=None,
                              cache_dir=tmp_path, unit_id="T1")
    assert len(client.calls) == 2


def test_synthesize_segment_force_bypasses_cache(tmp_path):
    client = _FakeClient()
    seg = audio.NarrationSegment(scene_id=1, raw_text="Hi", tts_text="Hi")
    audio.synthesize_segment(client, seg, "voice1", "model1",
                              previous_text=None, next_text=None,
                              cache_dir=tmp_path, unit_id="T1")
    audio.synthesize_segment(client, seg, "voice1", "model1",
                              previous_text=None, next_text=None,
                              cache_dir=tmp_path, unit_id="T1", force=True)
    assert len(client.calls) == 2


# ---------------------------------------------------------------------------
# synthesize_unit_audio — guardrails that don't need real audio
# ---------------------------------------------------------------------------

class _FakeConfig:
    def __init__(self, lanes, pronunciation=None):
        self._lanes = lanes
        self.pronunciation = pronunciation or {"spell_out": [], "replace": {}}

    def lane(self, name):
        return self._lanes[name]


def test_synthesize_unit_audio_raises_without_voice_id(tmp_path):
    plan = _plan([{"scene_id": 1, "card": "TitleCard", "headline": "Hi", "body": ""}])
    cfg = _FakeConfig({"season": {"voice_id": "", "model_id": ""}})
    with pytest.raises(RuntimeError, match="voice_id/model_id"):
        audio.synthesize_unit_audio(cfg, plan, client=_FakeClient())


def test_synthesize_unit_audio_raises_on_empty_plan(tmp_path):
    plan = _plan([{"scene_id": 1, "card": "DiagramCard", "asset": {"kind": "svg_library", "path": "x.svg"}}])
    cfg = _FakeConfig({"season": {"voice_id": "v1", "model_id": "m1"}})
    with pytest.raises(RuntimeError, match="no spoken text"):
        audio.synthesize_unit_audio(cfg, plan, client=_FakeClient())


# ---------------------------------------------------------------------------
# End-to-end assembly: real pydub, real (tiny, silent) mp3 clips, fake
# ElevenLabs client. Needs ffmpeg on PATH (pydub's decode/encode backend) —
# same environment dependency as the render/sync-fonts steps, so this is
# skipped rather than failed where ffmpeg isn't available.
# ---------------------------------------------------------------------------

pytest.importorskip("pydub")
import shutil as _shutil  # noqa: E402

_HAVE_FFMPEG = _shutil.which("ffmpeg") is not None


class _RealAudioFakeClient:
    """Like _FakeClient, but returns genuine (silent) mp3 bytes so pydub can
    actually decode and concatenate them — needed to exercise _assemble."""

    def __init__(self, ms_per_word: int = 400):
        from pydub import AudioSegment
        self._AudioSegment = AudioSegment
        self.ms_per_word = ms_per_word
        self.calls = []

    def _convert(self, voice_id, *, text, model_id, output_format, previous_text, next_text):
        import io
        self.calls.append(text)
        n_words = len(text.split())
        duration_ms = max(200, n_words * self.ms_per_word)
        clip = self._AudioSegment.silent(duration=duration_ms)
        buf = io.BytesIO()
        clip.export(buf, format="mp3")
        mp3_bytes = buf.getvalue()

        # Evenly spread each character across the clip — synthetic but
        # monotonic, which is all the retiming math needs to be correct.
        n = len(text)
        char_ms = duration_ms / max(n, 1)
        starts = [round(i * char_ms) for i in range(n)]
        durations = [round(char_ms)] * n
        alignment = _FakeAlignment(list(text), starts, durations)
        return types.SimpleNamespace(
            audio_base_64=__import__("base64").b64encode(mp3_bytes).decode("ascii"),
            alignment=alignment,
        )

    @property
    def text_to_speech(self):
        return types.SimpleNamespace(convert_with_timestamps=self._convert)


@pytest.mark.skipif(not _HAVE_FFMPEG, reason="pydub needs ffmpeg on PATH to decode/encode mp3")
def test_synthesize_unit_audio_retimes_scenes_and_writes_voice_file(tmp_path, monkeypatch):
    monkeypatch.setattr(audio, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(audio, "VOICE_OUT_DIR", tmp_path / "out" / "audio")

    plan = {
        "unit_id": "T1", "lane": "season", "fps": 30,
        "cta": {"tier": 1, "on_screen": "FOLLOW"},
        "scenes": [
            {"scene_id": 1, "card": "TitleCard", "headline": "Ninety-nine percent.",
             "body": "On training."},
            {"scene_id": 2, "card": "DiagramCard", "duration_frames": 60,
             "asset": {"kind": "svg_library", "path": "x.svg"}},  # silent beat, author-authored 2s hold
            {"scene_id": 3, "card": "TrapCard", "headline": "Safe?",
             "body": "Not if you tuned it.",
             "amber_spans": [{"field": "body", "start": 0, "end": 3, "reason": "trap"}]},
        ],
    }
    cfg = _FakeConfig({"season": {"voice_id": "v1", "model_id": "m1"}})
    client = _RealAudioFakeClient()

    result = audio.synthesize_unit_audio(cfg, plan, client=client, cache_dir=tmp_path / "cache")

    assert len(client.calls) == 2  # scenes 1 and 3 — scene 2 has no text, never called
    assert result["segments_synthesized"] == 2
    assert (tmp_path / "out" / "audio" / "T1_voice.mp3").exists()

    new_scenes = {s["scene_id"]: s for s in result["scenes"]}
    # scene 1 starts at 0
    assert new_scenes[1]["start_frame"] == 0
    # scene 2 (silent) keeps needing SOME duration — it wasn't dropped
    assert new_scenes[2]["duration_frames"] >= 0
    # scenes stay contiguous: each scene starts where the previous one ends
    assert new_scenes[2]["start_frame"] == new_scenes[1]["start_frame"] + new_scenes[1]["duration_frames"]
    assert new_scenes[3]["start_frame"] == new_scenes[2]["start_frame"] + new_scenes[2]["duration_frames"]
    # last scene gets the trailing hold added
    assert result["duration_frames"] == new_scenes[3]["start_frame"] + new_scenes[3]["duration_frames"]

    captions = result["captions"]
    by_text = {c["text"]: c for c in captions}
    assert by_text["Not"]["emphasis"] == "constraint"
    assert "emphasis" not in by_text["Safe?"]
    # captions from scene 3 must be offset by scene 1's clip length, not start at 0
    assert by_text["Safe?"]["start_frame"] > 0
