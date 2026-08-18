"""Phase 3 — real ElevenLabs voiceover, character-level timestamps, and
scene retiming from actual speech length.

Never calls an LLM and never invents a word. Every character sent to
ElevenLabs is either verbatim shot-plan text (a scene's headline/body, or
cta.spoken for the CTA scene) or a pronunciation substitution from
config/pronunciation.json, applied to the SPOKEN copy only — captions
always display the original text, never the substituted form (see
build_captions and cards/Captions.tsx's own docstring on why captions come
from ElevenLabs timestamps, not a transcriber).

One TTS call per scene, not one call for the whole script. That keeps this
stage idempotent and resumable (CLAUDE.md's "layered pipeline,
idempotent/resumable stages" standard): change slide 4's copy and only
slide 4's audio needs to be regenerated — everything else is served from
the out/audio_cache/<unit>/ cache, keyed by a hash of (voice_id, model_id,
tts_text). previous_text/next_text are still passed on every call so
ElevenLabs hears the surrounding sentence for prosody, even though each
clip is billed, cached, and can be individually invalidated.

Retiming: a shot plan's scene start_frame/duration_frames are a provisional
guess at pacing, made before anyone has heard the voice (by the LLM or a
human, in Cowork chat). This module overwrites them with the actual
boundaries the recorded speech lands on — a card holding on screen after
its line has finished, or cutting before it ends, is a worse defect than
disagreeing with the original guess. Scenes with no spoken line (a pure
visual beat — rare, but the schema allows a scene with only a DiagramCard
asset and no headline) keep their authored duration untouched and simply
shift to sit after whatever precedes them.
"""
from __future__ import annotations

import base64
import hashlib
import io
import json
import os
from dataclasses import dataclass
from pathlib import Path

from .config import REPO_ROOT, Config

SEGMENT_GAP_MS = 320          # silence inserted between one scene's line and the next
END_TAIL_FRAMES_DEFAULT = 24  # ~0.8s @30fps held on the final card after its line ends
OUTPUT_FORMAT = "mp3_44100_128"
CACHE_DIR_DEFAULT = REPO_ROOT / "out" / "audio_cache"
VOICE_OUT_DIR = REPO_ROOT / "out" / "audio"


@dataclass
class NarrationSegment:
    scene_id: int
    raw_text: str   # what's on screen / what captions show
    tts_text: str    # pronunciation-substituted — what's actually sent to ElevenLabs


# ---------------------------------------------------------------------------
# Pronunciation
# ---------------------------------------------------------------------------

_STRIP_CHARS = ".,;:!?’'\""


def apply_pronunciation(text: str, pronunciation: dict) -> str:
    """Spell out acronyms and apply literal replacements from
    config/pronunciation.json.

    Word-count preserving by construction: every substitution replaces
    exactly one whitespace-delimited token with exactly one other token
    (spaces inside a spelled-out acronym are dots, not spaces — "GDPR"
    becomes "G.D.P.R.", one token, not four). That's what keeps the raw and
    tts word lists index-aligned, which is what lets captions show "GDPR"
    while the voice says the letters — see build_captions.
    """
    replace = pronunciation.get("replace", {})
    spell_out = set(pronunciation.get("spell_out", []))

    def _sub_token(token: str) -> str:
        core = token.strip(_STRIP_CHARS)
        trailing = token[len(core):] if core and token.startswith(core) else ""
        if core in replace:
            return replace[core] + trailing
        if core and core.isupper() and core in spell_out:
            return ".".join(list(core)) + "." + trailing
        return token

    return " ".join(_sub_token(tok) for tok in text.split())


# ---------------------------------------------------------------------------
# Narration segments — what gets spoken, per scene
# ---------------------------------------------------------------------------

def _scene_raw_text(scene: dict, cta: dict | None) -> str:
    """The text a scene's line is built from. The CTA scene is the one
    exception: if cta.spoken is set, that's what's said aloud — headline/
    body on a CTACard are the on-screen line, which may differ from the
    spoken one (e.g. tier-2 CTAs are passive/on-screen-only; see
    cards/CTACard.tsx and Video_Pipeline_Setup_v1.0.md §1, CTA tiers)."""
    if scene.get("card") == "CTACard":
        spoken = (cta or {}).get("spoken")
        if spoken:
            return spoken.strip()
    parts = [scene.get("headline", "") or "", scene.get("body", "") or ""]
    return " ".join(p for p in parts if p).strip()


def build_narration_segments(shotplan: dict, pronunciation: dict) -> list[NarrationSegment]:
    """One segment per scene that has something to say, in scene order.
    Scenes with no headline/body/cta.spoken (a silent visual beat) are
    skipped — they keep their authored duration in the retiming pass."""
    cta = shotplan.get("cta")
    segments = []
    for scene in shotplan.get("scenes", []):
        raw = _scene_raw_text(scene, cta)
        if not raw:
            continue
        segments.append(NarrationSegment(
            scene_id=scene["scene_id"],
            raw_text=raw,
            tts_text=apply_pronunciation(raw, pronunciation),
        ))
    return segments


# ---------------------------------------------------------------------------
# Word-level timing from ElevenLabs' character alignment
# ---------------------------------------------------------------------------

def _word_spans(text: str) -> list[tuple[int, int]]:
    """Character [start, end) offsets of each whitespace-delimited word."""
    spans = []
    i = 0
    for word in text.split():
        i = text.index(word, i)
        spans.append((i, i + len(word)))
        i += len(word)
    return spans


def _word_times_ms(alignment: dict, text: str) -> list[tuple[int, int]]:
    """(start_ms, end_ms) per whitespace word, from ElevenLabs' `alignment`
    (never `normalized_alignment` — the latter is timed against
    post-normalisation text, e.g. digits expanded to words, and would drift
    out of index-alignment with our own word list)."""
    chars = alignment["chars"]
    if len(chars) != len(text):
        raise RuntimeError(
            f"ElevenLabs alignment has {len(chars)} characters but the text sent "
            f"had {len(text)} — cannot map word timings. This should only happen "
            f"if the SDK/API contract changed; do not silently guess offsets."
        )
    starts = alignment["char_start_times_ms"]
    durations = alignment["char_durations_ms"]
    ends = [s + d for s, d in zip(starts, durations)]
    out = []
    for w_start, w_end in _word_spans(text):
        out.append((min(starts[w_start:w_end]), max(ends[w_start:w_end])))
    return out


def _scene_word_origins(scene: dict, cta: dict | None) -> list[dict]:
    """Spoken-order word list, each tagged with where it came from in the
    shot plan: {'text', 'field', 'start', 'end'}. field/start/end are None
    for a CTA's spoken line — amber_spans are only ever defined against a
    scene's headline/body (see schemas/shotlist.schema.json), never
    against cta.spoken, so there is nothing to map a CTA word back to."""
    if scene.get("card") == "CTACard" and (cta or {}).get("spoken"):
        return [{"text": w, "field": None, "start": None, "end": None}
                for w in cta["spoken"].strip().split()]

    origins = []
    for field in ("headline", "body"):
        text = scene.get(field) or ""
        for start, end in _word_spans(text):
            origins.append({"text": text[start:end], "field": field, "start": start, "end": end})
    return origins


def _word_is_amber(word_origin: dict, amber_spans: list[dict]) -> bool:
    return _matching_amber_span(word_origin, amber_spans) is not None


def _matching_amber_span(word_origin: dict, amber_spans: list[dict]) -> dict | None:
    """The amber_spans entry (if any) that covers this word, so its `reason`
    can be carried onto the caption — G2's AMBER_CAPTION_UNJUSTIFIED check
    wants a caption's own `reason` field, not just `emphasis: "constraint"`.
    """
    if word_origin["field"] is None:
        return None
    for span in amber_spans:
        if span.get("field") != word_origin["field"]:
            continue
        if word_origin["start"] < span["end"] and word_origin["end"] > span["start"]:
            return span
    return None


def build_captions(shotplan: dict, timeline: dict) -> list[dict]:
    """timeline: {scene_id: (alignment_dict, start_ms, end_ms)} — the
    absolute position of each spoken scene's clip in the assembled
    voice.mp3 (see _assemble). One caption per spoken word. emphasis=
    'constraint' only for words whose source span falls inside an
    amber_spans entry — mirrors G2's own amber-is-constraint-only rule
    (pipeline/gates/brand.py AMBER_DECORATION) so captions can never
    paint amber for punch alone, the exact mistake CLAUDE.md and
    cards/Captions.tsx's docstring both call out.
    """
    fps = shotplan["fps"]
    cta = shotplan.get("cta")
    captions: list[dict] = []
    for scene in shotplan.get("scenes", []):
        entry = timeline.get(scene["scene_id"])
        if entry is None:
            continue
        alignment, seg_start_ms, _seg_end_ms = entry
        raw_text = _scene_raw_text(scene, cta)
        word_times = _word_times_ms(alignment, raw_text)
        origins = _scene_word_origins(scene, cta)
        amber_spans = scene.get("amber_spans", [])

        if len(word_times) != len(origins):
            raise RuntimeError(
                f"Scene {scene['scene_id']}: word count mismatch between ElevenLabs "
                f"alignment ({len(word_times)}) and shot-plan text ({len(origins)}). "
                f"apply_pronunciation should be word-count preserving — this means "
                f"either that guarantee broke, or the SDK response doesn't match "
                f"the text that was sent."
            )

        for (w_start_ms, w_end_ms), origin in zip(word_times, origins):
            caption = {
                "text": origin["text"],
                "start_frame": round((seg_start_ms + w_start_ms) / 1000 * fps),
                "end_frame": round((seg_start_ms + w_end_ms) / 1000 * fps),
            }
            matched_span = _matching_amber_span(origin, amber_spans)
            if matched_span is not None:
                caption["emphasis"] = "constraint"
                caption["reason"] = matched_span["reason"]
            captions.append(caption)
    return captions


# ---------------------------------------------------------------------------
# ElevenLabs calls, cached per scene
# ---------------------------------------------------------------------------

def _cache_paths(cache_dir: Path, unit_id: str, scene_id: int) -> tuple[Path, Path]:
    d = cache_dir / unit_id
    d.mkdir(parents=True, exist_ok=True)
    return d / f"scene_{scene_id}.mp3", d / f"scene_{scene_id}.json"


def _content_hash(tts_text: str, voice_id: str, model_id: str) -> str:
    return hashlib.sha256(f"{voice_id}|{model_id}|{tts_text}".encode("utf-8")).hexdigest()


def synthesize_segment(client, segment: NarrationSegment, voice_id: str, model_id: str, *,
                        previous_text: str | None, next_text: str | None,
                        cache_dir: Path, unit_id: str, force: bool = False) -> tuple[bytes, dict]:
    """Returns (mp3_bytes, alignment_dict) for one scene's line.

    Cached by a hash of (voice_id, model_id, tts_text) so re-running costs
    nothing unless one of those three actually changed, or --force is
    passed. This is the whole reason generation is per-scene rather than
    one call for the entire script — a hand-edit to one slide shouldn't
    require re-spending on the other nine.
    """
    mp3_path, meta_path = _cache_paths(cache_dir, unit_id, segment.scene_id)
    content_hash = _content_hash(segment.tts_text, voice_id, model_id)

    if not force and mp3_path.exists() and meta_path.exists():
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        if meta.get("content_hash") == content_hash:
            return mp3_path.read_bytes(), meta["alignment"]

    response = client.text_to_speech.convert_with_timestamps(
        voice_id,
        text=segment.tts_text,
        model_id=model_id,
        output_format=OUTPUT_FORMAT,
        previous_text=previous_text,
        next_text=next_text,
    )
    audio_bytes = base64.b64decode(response.audio_base_64)
    # The installed elevenlabs SDK's CharacterAlignmentResponseModel uses
    # `characters`/`character_start_times_seconds`/`character_end_times_seconds`
    # (seconds, start+end) — not the `chars`/`char_start_times_ms`/
    # `char_durations_ms` (ms, start+duration) shape this module was written
    # against. Converted once here, at the API boundary, so every downstream
    # consumer (_word_times_ms etc.) keeps working against ms/duration
    # without knowing the SDK changed underneath it.
    starts_ms = [s * 1000 for s in response.alignment.character_start_times_seconds]
    ends_ms = [e * 1000 for e in response.alignment.character_end_times_seconds]
    alignment = {
        "chars": response.alignment.characters,
        "char_start_times_ms": starts_ms,
        "char_durations_ms": [e - s for s, e in zip(starts_ms, ends_ms)],
    }
    mp3_path.write_bytes(audio_bytes)
    meta_path.write_text(json.dumps({"content_hash": content_hash, "alignment": alignment}), encoding="utf-8")
    return audio_bytes, alignment


# ---------------------------------------------------------------------------
# Assembly: concatenate clips, retime scenes, build captions
# ---------------------------------------------------------------------------

def _assemble(shotplan: dict, clips: list[tuple[NarrationSegment, bytes, dict]],
              voice_out_path: Path) -> dict:
    from pydub import AudioSegment

    fps = shotplan["fps"]
    gap = AudioSegment.silent(duration=SEGMENT_GAP_MS)

    timeline: dict[int, tuple[dict, int, int]] = {}
    combined = AudioSegment.empty()
    cursor_ms = 0
    for i, (seg, audio_bytes, alignment) in enumerate(clips):
        clip = AudioSegment.from_file(io.BytesIO(audio_bytes), format="mp3")
        timeline[seg.scene_id] = (alignment, cursor_ms, cursor_ms + len(clip))
        combined += clip
        cursor_ms += len(clip)
        if i < len(clips) - 1:
            combined += gap
            cursor_ms += SEGMENT_GAP_MS

    voice_out_path.parent.mkdir(parents=True, exist_ok=True)
    combined.export(voice_out_path, format="mp3")

    # --- retime scenes against the real speech boundaries ------------------
    new_scenes = []
    cursor_frame = 0
    scenes = shotplan.get("scenes", [])
    for idx, scene in enumerate(scenes):
        is_last = idx == len(scenes) - 1
        entry = timeline.get(scene["scene_id"])
        if entry is not None:
            _alignment, start_ms, end_ms = entry
            start_frame = round(start_ms / 1000 * fps)
            duration_frames = round((end_ms - start_ms) / 1000 * fps)
            if is_last:
                duration_frames += END_TAIL_FRAMES_DEFAULT
            # keep the timeline contiguous even if per-scene rounding drifted
            # us slightly behind where the previous scene actually ended
            start_frame = max(start_frame, cursor_frame)
        else:
            start_frame = cursor_frame
            duration_frames = scene["duration_frames"]  # silent beat — author's call stands

        new_scene = dict(scene)
        new_scene["start_frame"] = start_frame
        new_scene["duration_frames"] = duration_frames
        new_scenes.append(new_scene)
        cursor_frame = start_frame + duration_frames

    captions = build_captions(shotplan, timeline)

    return {
        "voice_file": voice_out_path.relative_to(REPO_ROOT).as_posix(),
        "scenes": new_scenes,
        "captions": captions,
        "duration_frames": cursor_frame,
        "segments_synthesized": len(clips),
    }


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def synthesize_unit_audio(cfg: Config, shotplan: dict, *, client=None,
                           cache_dir: Path | None = None, force: bool = False) -> dict:
    """The Phase 3 entry point. Pure with respect to the shot plan — never
    mutates it, returns a result dict for the caller to merge in (see
    produce.py's apply_audio_result). Never generates or edits spoken
    text; only synthesizes and times what the shot plan already contains.

    Raises RuntimeError if the lane's voice_id/model_id aren't pinned in
    lanes.yaml, if ELEVENLABS_API_KEY isn't set, or if the shot plan has no
    spoken text anywhere to synthesize.
    """
    lane_cfg = cfg.lane(shotplan["lane"])
    voice_id = lane_cfg.get("voice_id")
    model_id = lane_cfg.get("model_id")
    if not voice_id or not model_id:
        raise RuntimeError(
            f"{shotplan['lane']}.voice_id/model_id not set in lanes.yaml — "
            f"cannot synthesize audio. See Video_Pipeline_Setup_v1.0.md §2.2."
        )

    if client is None:
        from elevenlabs.client import ElevenLabs
        api_key = os.environ.get("ELEVENLABS_API_KEY")
        if not api_key:
            raise RuntimeError("ELEVENLABS_API_KEY not set. Copy .env.example to .env and fill it in.")
        client = ElevenLabs(api_key=api_key)

    cache_dir = cache_dir or CACHE_DIR_DEFAULT
    segments = build_narration_segments(shotplan, cfg.pronunciation)
    if not segments:
        raise RuntimeError("Shot plan has no spoken text anywhere — nothing to synthesize.")

    clips = []
    for i, seg in enumerate(segments):
        prev_text = segments[i - 1].tts_text if i > 0 else None
        next_text = segments[i + 1].tts_text if i + 1 < len(segments) else None
        audio_bytes, alignment = synthesize_segment(
            client, seg, voice_id, model_id,
            previous_text=prev_text, next_text=next_text,
            cache_dir=cache_dir, unit_id=shotplan["unit_id"], force=force,
        )
        clips.append((seg, audio_bytes, alignment))

    voice_out_path = VOICE_OUT_DIR / f"{shotplan['unit_id']}_voice.mp3"
    result = _assemble(shotplan, clips, voice_out_path)
    result["voice_id"] = voice_id
    result["model_id"] = model_id
    return result
