"""G3 — Audio gate.

Checks that don't need a human ear: words-per-second in range
(config/pipeline.yaml audio.target_wps), voice_id/model_id match the
pinned lane config, and — if the rendered voice.mp3 already exists on
disk — no clipping. Duration-in-bounds is G2's job (pipeline/gates/
brand.py DURATION_OUT_OF_BOUNDS / BLUEPRINT_TOO_SHORT / SEASON_TOO_LONG);
this gate only covers pace and audio identity/quality, per
Video_Pipeline_Setup_v1.0.md §6.

WPS/id checks are pure and run on any shot plan, synthesized or not —
`plan` calls this before audio exists at all, so it always passes
voice_file_abspath=None and only ever sees the WPS/id findings. `run`
calls it again after Phase 3 has produced a real voice.mp3, this time with
a path, so clipping gets checked too.

The clipping check is best-effort: it's a warn (never a fail) if the file
isn't on disk yet, or if pydub/ffmpeg can't decode it — same reasoning as
sync-fonts and the Remotion render needing the real machine. An
environment gap here should never block a shot plan from passing gates
that have nothing to do with the environment.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass
class Finding:
    severity: str  # "fail" | "warn"
    code: str
    message: str


def _spoken_word_count(shotplan: dict) -> int:
    """Counts words in the RAW (on-screen/caption) text, not the
    pronunciation-substituted TTS text — this gate is about how a viewer
    experiences pace, and a viewer never sees "G.D.P.R.", they see "GDPR"."""
    from ..audio import _scene_raw_text

    cta = shotplan.get("cta")
    total = 0
    for scene in shotplan.get("scenes", []):
        total += len(_scene_raw_text(scene, cta).split())
    return total


def check(cfg, unit, shotplan: dict, *, voice_file_abspath: Path | None = None) -> list[Finding]:
    findings: list[Finding] = []
    lane_cfg = cfg.lane(shotplan["lane"])
    audio = shotplan.get("audio") or {}

    # --- voice / model identity ---------------------------------------------
    if audio.get("voice_id") and audio["voice_id"] != lane_cfg.get("voice_id"):
        findings.append(Finding("fail", "VOICE_ID_MISMATCH",
            f"Shot plan voice_id {audio['voice_id']!r} does not match lanes.yaml's "
            f"pinned {lane_cfg.get('voice_id')!r} for {shotplan['lane']}. Episode 40 "
            f"sounding different from episode 1 is exactly what pinning prevents."))
    if audio.get("model_id") and audio["model_id"] != lane_cfg.get("model_id"):
        findings.append(Finding("fail", "MODEL_ID_MISMATCH",
            f"Shot plan model_id {audio['model_id']!r} does not match lanes.yaml's "
            f"pinned {lane_cfg.get('model_id')!r} for {shotplan['lane']}."))

    # --- words per second ----------------------------------------------------
    fps = shotplan.get("fps", 30)
    duration_frames = shotplan.get("duration_frames", 0)
    if duration_frames and fps:
        duration_s = duration_frames / fps
        words = _spoken_word_count(shotplan)
        wps = words / duration_s
        lo, hi = cfg.pipeline.get("audio", {}).get("target_wps", [2.2, 2.8])
        if wps < lo or wps > hi:
            findings.append(Finding("warn", "WPS_OUT_OF_RANGE",
                f"{wps:.2f} words/sec against a {lo}-{hi} target "
                f"({'rushed' if wps > hi else 'draggy'} pacing at the current "
                f"duration_frames). Advisory before audio exists; worth an actual "
                f"listen once it does."))

    # --- clipping (best-effort) ----------------------------------------------
    if voice_file_abspath is not None:
        if not voice_file_abspath.exists():
            findings.append(Finding("warn", "AUDIO_NOT_SYNTHESIZED",
                "No voice file on disk yet — clipping not checked. "
                "Run `produce.py audio --unit <ID>` first."))
        else:
            try:
                from pydub import AudioSegment
                clip = AudioSegment.from_file(voice_file_abspath)
                ceiling = cfg.pipeline.get("audio", {}).get("peak_ceiling_db", -1.0)
                if clip.max_dBFS > ceiling:
                    findings.append(Finding("fail", "CLIPPING",
                        f"Peak {clip.max_dBFS:.1f}dBFS exceeds ceiling {ceiling}dBFS."))
            except Exception as e:  # pydub/ffmpeg unavailable, or a bad file
                findings.append(Finding("warn", "CLIPPING_CHECK_UNAVAILABLE",
                    f"Could not analyse {voice_file_abspath.name}: {e}. "
                    f"Usually means ffmpeg isn't on PATH here — check with `produce.py doctor`."))

    return findings


def passed(findings: list[Finding]) -> bool:
    return not any(f.severity == "fail" for f in findings)
