#!/usr/bin/env python
"""FundaForge Video Renderer — single entry point.

    python produce.py doctor
    python produce.py plan   --unit S1E05
    python produce.py audio  --unit S1E05
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
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import jsonschema

from pipeline import audio as audiomod
from pipeline import config as cfgmod
from pipeline import metadata as metadatamod
from pipeline import source
from pipeline.gates import audio_gate, brand, fidelity, humanization

REPO_ROOT = Path(__file__).resolve().parent
REMOTION_DIR = REPO_ROOT / "remotion"


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

    api_key = os.environ.get("ELEVENLABS_API_KEY")
    print(f"  {'ok  ' if api_key else 'FAIL'}  ELEVENLABS_API_KEY -> {'set' if api_key else 'missing from .env'}")
    ok &= bool(api_key)

    ffmpeg_path = shutil.which("ffmpeg")
    mark = "ok  " if ffmpeg_path else "WARN"
    print(f"  {mark}  ffmpeg on PATH -> {ffmpeg_path or 'not found — audio concat/clipping check will fail'}")

    print("\n  TODO: font presence, Remotion install reachable from this machine")
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

    # voice_file_abspath is derived from the shot plan itself, not passed in —
    # before Phase 3 has run, audio.voice_file is unset and this call only
    # exercises the WPS/id checks; once `produce.py audio` has written a real
    # voice.mp3 and set audio.voice_file, every later `plan`/`run` re-check of
    # the same shot plan automatically picks up the clipping check too.
    audio = shotplan.get("audio") or {}
    voice_file_abspath = (REPO_ROOT / audio["voice_file"]) if audio.get("voice_file") else None
    audio_findings = audio_gate.check(cfg, unit, shotplan, voice_file_abspath=voice_file_abspath)
    _print_findings("audio", audio_findings)

    any_fail = (
        not fidelity.passed(fidelity_findings)
        or not brand.passed(brand_findings)
        or not audio_gate.passed(audio_findings)
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


def sync_diagram_assets(cfg, shotplan: dict) -> list[str]:
    """Copy any svg_library diagram assets a shot plan references into
    remotion/public/diagrams/, resolving by filename against the real
    02_Vector_Library folder tree.

    Walks the folder rather than trusting 02_Vector_Library/Asset_Register.md
    — that file is documentation only and known stale (see
    Carousel_Feedback_Log.md, 18 Aug 2026 entry); the carousel renderer
    itself resolves by filesystem walk, not by reading the register, so this
    mirrors the one thing that's actually authoritative.

    Raises FileNotFoundError (never silently skips) if a referenced asset
    can't be found anywhere in the vector library — better to fail the
    render loudly than ship a card with a missing diagram.
    """
    vector_lib = cfg.ro("vector_library")
    dest_dir = REMOTION_DIR / "public" / "diagrams"
    dest_dir.mkdir(parents=True, exist_ok=True)

    synced: list[str] = []
    missing: list[str] = []
    for scene in shotplan.get("scenes", []):
        asset = scene.get("asset")
        if not asset or asset.get("kind") != "svg_library":
            continue
        filename = Path(asset["path"]).name
        dest = dest_dir / filename
        if dest.exists():
            synced.append(filename)
            continue
        matches = list(vector_lib.rglob(filename))
        if not matches:
            missing.append(filename)
            continue
        shutil.copyfile(matches[0], dest)
        synced.append(filename)

    if missing:
        raise FileNotFoundError(
            f"Diagram asset(s) not found anywhere under {vector_lib}: {missing}. "
            f"Cannot render without them — check the filename in the shot plan, "
            f"or this may be carousel feedback (log it, don't invent the file here)."
        )
    return synced


def sync_music_asset(cfg, shotplan: dict) -> str | None:
    """Copy the lane's music bed into remotion/public/ if referenced.

    music_file paths in a shot plan are relative to the repo root (e.g.
    'assets/music/blueprint_bed.mp3', matching config/lanes.yaml) — Remotion's
    staticFile() only serves from remotion/public/, so this must be synced
    there before every render, same idea as sync-fonts.mjs for brand fonts.
    """
    music_file = (shotplan.get("audio") or {}).get("music_file")
    if not music_file:
        return None

    src = REPO_ROOT / music_file
    dest = REMOTION_DIR / "public" / music_file
    if not src.exists():
        raise FileNotFoundError(f"Music bed not found: {src}")

    dest.parent.mkdir(parents=True, exist_ok=True)
    if not dest.exists() or dest.stat().st_mtime < src.stat().st_mtime:
        shutil.copyfile(src, dest)
    return music_file


def sync_voice_asset(shotplan: dict) -> str | None:
    """Copy the unit's synthesized voiceover into remotion/public/, same
    idea and same shape as sync_music_asset — pipeline.audio writes the
    real file to out/audio/<unit>_voice.mp3 (source of truth, not
    Remotion-servable); this puts a copy where staticFile() can reach it.
    """
    voice_file = (shotplan.get("audio") or {}).get("voice_file")
    if not voice_file:
        return None

    src = REPO_ROOT / voice_file
    dest = REMOTION_DIR / "public" / voice_file
    if not src.exists():
        raise FileNotFoundError(
            f"Voice file not found: {src}. Run `produce.py audio --unit "
            f"{shotplan.get('unit_id')}` first."
        )

    dest.parent.mkdir(parents=True, exist_ok=True)
    if not dest.exists() or dest.stat().st_mtime < src.stat().st_mtime:
        shutil.copyfile(src, dest)
    return voice_file


def next_draft_version(unit_id: str) -> int:
    """Next version number for out/drafts/<unit>/<unit>_v{N}.mp4.

    Never overwrites a previous draft — each render iteration gets its own
    number so earlier attempts stay around for comparison, per the review
    workflow (v1 vs v2 vs v3, not one file clobbered each time).
    """
    drafts_dir = REPO_ROOT / "out" / "drafts" / unit_id
    drafts_dir.mkdir(parents=True, exist_ok=True)
    pattern = re.compile(rf"^{re.escape(unit_id)}_v(\d+)\.mp4$")
    versions = [int(m.group(1)) for p in drafts_dir.glob(f"{unit_id}_v*.mp4")
                if (m := pattern.match(p.name))]
    return max(versions, default=0) + 1


def render_unit(unit_id: str, shotplan_path: Path) -> Path:
    """Invoke the actual Remotion render as a subprocess.

    Runs sync-fonts first, same as package.json's own scripts always do —
    Chromium needs the brand fonts present in remotion/public/fonts/ before
    it can render text in them. Raises RuntimeError with the tail of stderr
    on any failure; never swallows a render error silently.
    """
    version = next_draft_version(unit_id)
    output_path = (REPO_ROOT / "out" / "drafts" / unit_id / f"{unit_id}_v{version}.mp4")

    npm_exe = shutil.which("npm")
    if npm_exe is None:
        raise RuntimeError("npm not found on PATH")
    sync_fonts = subprocess.run(
        [npm_exe, "run", "sync-fonts"], cwd=REMOTION_DIR,
        capture_output=True, text=True,
    )
    if sync_fonts.returncode != 0:
        raise RuntimeError(f"sync-fonts failed:\n{sync_fonts.stdout}\n{sync_fonts.stderr}")

    npx_exe = shutil.which("npx")
    if npx_exe is None:
        raise RuntimeError("npx not found on PATH")
    cmd = [
        npx_exe, "remotion", "render", "src/index.ts", "Short",
        str(output_path.resolve()),
        f"--props={shotplan_path.resolve()}",
    ]
    result = subprocess.run(cmd, cwd=REMOTION_DIR, capture_output=True, text=True)
    if result.returncode != 0:
        tail = (result.stdout + "\n" + result.stderr)[-3000:]
        raise RuntimeError(f"Remotion render failed (exit {result.returncode}):\n{tail}")

    return output_path


def run_unit(cfg, unit_id: str, *, confirmed: bool = False,
             shotplans_dir: Path | None = None) -> int:
    """Render an already-validated, already-approved shot plan.

    Never generates or edits a shot plan. Re-runs the same gate check `plan`
    uses — a shot plan approved once could have been hand-edited since, and
    re-checking is cheap compared to what a bad render costs. Refuses to
    proceed on any fail-severity gate finding, AND separately refuses to
    proceed for a lane requiring human_script_review unless `confirmed` is
    explicitly set — gates passing is necessary, not sufficient, and that
    rule doesn't get to be silently bypassed by a clean gate run.
    """
    shotplans_dir = shotplans_dir or (REPO_ROOT / "out" / "shotplans")
    shotplan_path = shotplans_dir / f"{unit_id}_shotplan.json"

    print(f"--- validating {unit_id} before render ---")
    gate_exit = validate_shotplan(cfg, unit_id, shotplans_dir=shotplans_dir)
    if gate_exit != 0:
        print(f"\n  Refusing to render: {unit_id}'s shot plan does not pass the gates. "
              f"Fix it and re-run `plan --unit {unit_id}` first.")
        return gate_exit

    unit = source.load_unit(cfg, unit_id)
    lane_cfg = cfg.lane(unit.lane)
    if lane_cfg.get("human_script_review") and not confirmed:
        print(f"\n  Refusing to render: {unit.lane} requires human sign-off before "
              f"render (gates passing is necessary, not sufficient). Re-run with "
              f"--confirmed once a human has read the shot plan against the CSV.")
        return 1

    shotplan = json.loads(shotplan_path.read_text(encoding="utf-8"))

    if not (shotplan.get("audio") or {}).get("voice_file"):
        print(f"\n  Refusing to render: {unit_id} has no synthesized voiceover yet. "
              f"Run `produce.py audio --unit {unit_id}` first — real ElevenLabs audio "
              f"is what the scene timings and captions get built from; a render "
              f"without it would use nothing but the author's guessed frame counts.")
        return 1

    print(f"\n--- syncing render assets for {unit_id} ---")
    try:
        diagrams = sync_diagram_assets(cfg, shotplan)
        music = sync_music_asset(cfg, shotplan)
        voice = sync_voice_asset(shotplan)
    except FileNotFoundError as e:
        print(f"  [FAIL] asset sync: {e}")
        return 1
    print(f"  diagrams: {diagrams or 'none referenced'}")
    print(f"  music: {music or 'none referenced'}")
    print(f"  voice: {voice}")

    print(f"\n--- rendering {unit_id} ---")
    try:
        output_path = render_unit(unit_id, shotplan_path)
    except RuntimeError as e:
        print(f"  [FAIL] render: {e}")
        return 1

    print(f"\n  Draft written: {output_path}")
    print(f"  This is a DRAFT for review, not an approved final. Watch it, then say "
          f"what to fix, or that it's good — approved output is a separate step, "
          f"never automatic.")

    # Per Sri (19 Aug 2026): draft YouTube upload metadata alongside every
    # render, same folder as the video. Never blocks the render on failure —
    # the video is the primary artifact; metadata is a review-and-paste-in
    # convenience on top of it, not a gate. Write-once per file (19 Aug 2026,
    # follow-up): a later re-render (v2, v3, ...) never overwrites a .txt Sri
    # may have already opened and hand-edited — see metadata.write_metadata's
    # own docstring.
    try:
        meta_results = metadatamod.write_metadata(shotplan, cfg, output_path.parent)
        print(f"\n  YouTube metadata (review before pasting into Studio "
              f"— nothing here has been uploaded, published, or sent):")
        for label, result in meta_results.items():
            status = "written" if result.written else "already exists, left as-is"
            print(f"    {label:15s} -> {result.path}  [{status}]")
    except Exception as e:
        print(f"\n  [WARN] metadata drafting failed, video draft is unaffected: {e}")

    return 0


def apply_audio_result_to_shotplan(shotplan: dict, result: dict) -> dict:
    """Merge a pipeline.audio.synthesize_unit_audio() result into a COPY of
    the shot plan. Never mutates the caller's dict — same defensive shape
    as everything else that touches an already-authored plan."""
    updated = dict(shotplan)
    updated["audio"] = {
        **(shotplan.get("audio") or {}),
        "voice_file": result["voice_file"],
        "voice_id": result["voice_id"],
        "model_id": result["model_id"],
    }
    updated["scenes"] = result["scenes"]
    updated["captions"] = result["captions"]
    updated["duration_frames"] = result["duration_frames"]
    return updated


def run_audio_for_unit(cfg, unit_id: str, *, force: bool = False,
                        shotplans_dir: Path | None = None) -> int:
    """Phase 3: synthesize real ElevenLabs audio for an already-gate-passing
    shot plan, retime its scenes against the actual speech, build captions
    from ElevenLabs' own character timestamps, and write the result back to
    the same shot-plan file.

    Costs real ElevenLabs credits (cached per scene — see pipeline/audio.py
    — so a second run with unchanged text/voice/model is free). Gates are
    checked first specifically to avoid spending on a plan that would be
    rejected anyway; this does NOT also require --confirmed the way `run`
    does, because synthesizing audio doesn't publish or send anything and
    introduces no new claims — it only speaks the words already approved
    (or not yet approved) in the plan. `run` still refuses to render until
    both gates pass AND (for human-review lanes) --confirmed is set.
    """
    shotplans_dir = shotplans_dir or (REPO_ROOT / "out" / "shotplans")
    shotplan_path = shotplans_dir / f"{unit_id}_shotplan.json"

    print(f"--- validating {unit_id} before spending on audio ---")
    gate_exit = validate_shotplan(cfg, unit_id, shotplans_dir=shotplans_dir)
    if gate_exit != 0:
        print(f"\n  Refusing to synthesize: {unit_id}'s shot plan does not pass the "
              f"gates. Fix it and re-run `plan --unit {unit_id}` first — no point "
              f"spending ElevenLabs credits on a plan that's going to be rejected.")
        return gate_exit

    shotplan = json.loads(shotplan_path.read_text(encoding="utf-8"))

    print(f"\n--- synthesizing voiceover for {unit_id} ---")
    try:
        result = audiomod.synthesize_unit_audio(cfg, shotplan, force=force)
    except RuntimeError as e:
        print(f"  [FAIL] audio: {e}")
        return 1

    print(f"  {result['segments_synthesized']} scene(s) synthesized/cached")
    print(f"  voice: {result['voice_file']}")
    print(f"  retimed duration: {result['duration_frames']} frames "
          f"({result['duration_frames'] / shotplan['fps']:.1f}s)")

    updated = apply_audio_result_to_shotplan(shotplan, result)
    shotplan_path.write_text(json.dumps(updated, indent=2), encoding="utf-8")
    print(f"\n  Shot plan updated in place: {shotplan_path}")
    print(f"  Scene timings and captions now reflect the real recording, not the "
          f"authored guess. Re-run `plan --unit {unit_id}` if you want to see the "
          f"gates (including clipping) against the actual audio before rendering.")
    return 0


def cmd_audio(args) -> int:
    if not args.unit:
        print("  --unit is required.")
        return 1
    cfg = cfgmod.load()
    return run_audio_for_unit(cfg, args.unit, force=args.force)


def cmd_run(args) -> int:
    if args.season is not None:
        print("  --season batch mode not yet implemented — use --unit for now, "
              "one at a time, per the agreed review workflow.")
        return 1
    if not args.unit:
        print("  --unit is required.")
        return 1

    cfg = cfgmod.load()
    return run_unit(cfg, args.unit, confirmed=args.confirmed)


def cmd_drift(_args) -> int:
    print("  TODO Phase 6: compare stored csv_sha256 against current CSVs")
    return 0


def main() -> int:
    p = argparse.ArgumentParser(prog="produce")
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("doctor").set_defaults(fn=cmd_doctor)

    sp = sub.add_parser("plan");  sp.add_argument("--unit", required=True); sp.set_defaults(fn=cmd_plan)
    sa = sub.add_parser("audio")
    sa.add_argument("--unit", required=True)
    sa.add_argument("--force", action="store_true",
                     help="Re-synthesize every scene even if a cached, unchanged "
                          "clip already exists.")
    sa.set_defaults(fn=cmd_audio)
    sr = sub.add_parser("run")
    sr.add_argument("--unit"); sr.add_argument("--season", type=int)
    sr.add_argument("--confirmed", action="store_true",
                     help="Human has read the shot plan against the CSV and signs off. "
                          "Required for any lane with human_script_review: true.")
    sr.set_defaults(fn=cmd_run)
    sub.add_parser("drift").set_defaults(fn=cmd_drift)

    args = p.parse_args()
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
