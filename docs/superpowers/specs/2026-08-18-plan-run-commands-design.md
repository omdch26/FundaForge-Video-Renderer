# Build `produce.py plan` and `run` — Phase 2/4 pipeline commands

**Date:** 2026-08-18
**Status:** Approved

## Context

Remotion bring-up is done (real fonts, all five card types, diagram
letterboxing solved, merged to main). `produce.py`'s `plan` and `run`
subcommands are still stubs. Per `Video_Pipeline_Setup_v1.0.md` §8 (build
order), this is Phase 2 (script generation + fidelity gate) and Phase 4
(asset resolution + shot list + full render), skipping Phase 3 (audio —
`ELEVENLABS_API_KEY` is empty in `.env`, nothing wired up yet).

Already built and reused as-is: `pipeline/config.py`, `pipeline/source.py`,
`pipeline/gates/fidelity.py`, `pipeline/gates/brand.py`. All four were
inspected against real data (BP34) during design and behave as documented.

## Goal

Implement `pipeline/script.py`, `pipeline/assets.py`, `pipeline/shotlist.py`,
`pipeline/render.py`, `pipeline/tracker.py`, and wire `produce.py plan`/`run`
to use them — producing a real, gate-checked, schema-valid shotplan and a
rendered draft mp4 for a unit, using BP34 as the proof case.

## Non-goals

- `pipeline/audio.py`, `pipeline/gates/audio_gate.py`, `pipeline/meta.py`,
  `pipeline/drift.py`, `pipeline/state.py` — explicitly later phases per the
  setup doc's own structure.
- Any LLM call. Phase 2 script generation is fully deterministic (see
  Decision 1).
- Deciding the voice-sample audition-vs-cloning question — flagged back to
  Sri, not decided here (moot for this build since audio.py doesn't exist
  yet, but Sri asked not to have it decided by default).
- YouTube upload, SRT export, metadata generation.

## Decisions locked during brainstorming

1. **No LLM in Phase 2.** `script.py` maps CSV rows to scenes deterministically:
   `headline`/`body` are the CSV's own `header_text`/`body_text`, unrewritten.
   This means the fidelity gate's hedge-preservation check can never fail on
   a Phase-2-generated script, because nothing was paraphrased — correct and
   honest for this phase. LLM-driven compression (needed once voiceover
   phrasing has to differ from on-screen text) is Phase 3's problem.

2. **`gates/brand.py` runs at both `plan` and `run` time.** It only inspects
   the shotlist JSON (hex codes, font-family strings, `amber_spans` reasons,
   accent, dimensions, `duration_frames`, kicker presence) — there is no
   pixel-level safe-area check in the current code despite the setup doc
   listing "safe areas" as a G2 concern. Since it's pure, cheap JSON
   inspection, `plan` runs it early (catch a wrong accent or off-palette hex
   before spending a render) and `run` re-runs it against the same shotlist
   post-render as the authoritative gate.

3. **`audio.voice_id`/`model_id` are always populated in the shotlist from
   `lanes.yaml`'s pinned per-lane values**, even when no audio has been
   generated (`voice_file: null`). They're config, not generated output, so
   they're always available. No schema change needed for these two fields.

4. **`schemas/shotlist.schema.json`'s `audio.voice_file` is widened to
   `["string", "null"]`.** `remotion/src/types.ts` and `Short.tsx` already
   treat it as nullable; the schema was the side out of sync. One-line,
   backward-compatible fix.

5. **Scene `duration_frames` is word-count-based**, using
   `pipeline.yaml`'s existing `audio.target_wps` (2.2-2.8, midpoint 2.5) as
   a reading-time estimate: `frames ≈ (word_count / 2.5) * fps`, clamped to
   a sensible per-card floor (TrapCard needs headroom for its answer-beat).
   Matches the setup doc's "content-driven, not fixed" duration principle
   and gives G2's duration-band warnings something real to check even before
   Phase 3 audio exists.

## Approach

### `pipeline/script.py`

`build_script(unit: Unit) -> dict` — one scene per slide (10 slides, 10
scenes; no folding/merging). Card type per slide:

| slide_type | card |
|---|---|
| `Hook` (slide 1) | `TitleCard` |
| `Interview trap` / `Regulator's question` (slide 9) | `TrapCard` |
| `CTA` (slide 10) | `CTACard` |
| anything else, `names_asset` set | `DiagramCard` |
| anything else, no asset | `BodyCard` |

`headline` = `slide.header_text`, `body` = `slide.body_text`, both verbatim.
CTA slide strips Instagram keyword mechanics: if `unit.cta_type == "keyword"`,
the on-screen/spoken CTA text is rewritten to a plain tier-1/2 CTA per
`lanes.yaml`'s `cta_tier_default` — the keyword itself is dropped, never
carried through. Output shape matches what `gates/fidelity.check()` expects:
`{"lane": unit.lane, "scenes": [{"slide_refs": [n], "voiceover": f"{header} {body}"}, ...]}`.

### `pipeline/assets.py`

`resolve_asset(slide: Slide, cfg: Config, unit_id: str) -> SceneAsset | None`.

1. If `slide.names_asset` is set: walk `02_Vector_Library` (`os.walk`,
   collect `*.svg` by stem — mirrors `batch_render_season.py` per setup doc
   §10, register is documentation only, never trusted as a list). If found,
   return `{"kind": "svg_library", "path": <relative path under
   assets/diagrams or copied into place>, "strip_backing_rect": True,
   "animate": "scale_in"}`.
2. If not found in the library, check `assets/manual/<unit_id>/` for a
   matching manual drop (`{"kind": "manual_drop", "path": ..., "slot":
   f"{unit_id}_s{slide.slide_number:02d}_..."}`).
3. If neither resolves, return `None` — type-only card, always valid,
   matches the schema's own description of the `asset` field.

The resolved SVG's actual bytes get copied into
`remotion/public/diagrams/<stem>.svg` (mirroring what the Remotion bring-up
work already did manually for `Drift_Types_Three.svg`) so `staticFile()`
can find it — never edits the source in `02_Vector_Library`.

### `pipeline/shotlist.py`

`build_shotlist(unit: Unit, script: dict, cfg: Config) -> dict`.

- Assigns `start_frame`/`duration_frames` sequentially per scene using the
  word-count/wps estimate (Decision 5).
- Resolves `amber_spans`: for the trap/regulator scene only, finds character
  offsets of any `fidelity.HEDGE_MARKERS` string present in that scene's
  `headline`/`body` and emits an `amber_spans` entry with `reason` set from
  the schema's enum (`"trap"` for season, `"regulator_question"` for
  blueprint) — reuses the gate's own marker list so the video's visual
  emphasis and the gate's textual check are driven by the same source of
  truth, not two independent guesses.
- Sets `accent`/`kicker`/`audio.voice_id`/`audio.model_id`/`audio.music_file`
  from `cfg.lane(unit.lane)` and `cfg.accent_hex(unit.lane)`.
  `audio.voice_file` is `null` (Decision 3/4).
- Sets `cta` block from `unit.cta_type`/`unit.keyword`, tier from
  `lanes.yaml`'s `cta_tier_default`.
- Sets `source` block: `csv_path`, `csv_sha256` (already computed by
  `source.load_unit`), `generated_at` (ISO 8601 UTC now).
- **Validates the assembled dict against `schemas/shotlist.schema.json` via
  `jsonschema.validate()` before returning.** A validation failure is a
  build bug, not a soft warning — raises, does not write a broken file.

### `pipeline/render.py`

`render(shotlist_path: Path, out_path: Path) -> None`. Invokes:

```
npx remotion render src/index.ts Short <out_path> --props=<shotlist_path>
```

via `subprocess.run(..., cwd=REPO_ROOT / "remotion", check=True)`. Confirmed
against `remotion/package.json`'s existing `dummy` script, which uses this
exact invocation shape. After the call returns, checks `out_path.exists()`
and `out_path.stat().st_size > 0` — raises with a clear message if not
(mirrors the same sanity check used during the Remotion bring-up work).

### `pipeline/tracker.py`

`update_status(cfg: Config, unit_id: str, status: str, notes: str | None =
None) -> None`. Opens `Unit_Index.xlsx` with `openpyxl` in normal (writable)
mode, re-reads the current sheet state immediately before writing (avoid
clobbering a concurrent manual edit), finds the row by `unit_id`, writes only
`shorts_status` and `shorts_notes` columns, saves. Touches no other column
and no other row.

### `produce.py plan --unit <ID>`

1. `source.load_unit(cfg, unit_id)`.
2. If `unit.ig_status.lower() != "published"`: print a warning, continue
   (never block on this).
3. `script.build_script(unit)`.
4. `gates.fidelity.check(unit, script)` → print every finding; if any
   `severity == "fail"`, print a clear failure summary and return a nonzero
   exit code without writing a shotplan.
5. `shotlist.build_shotlist(unit, script, cfg)` (internally calls
   `assets.resolve_asset` per scene, and validates against the schema).
6. `gates.brand.check(cfg, unit, shotlist)` → print every finding; any
   `severity == "fail"` is a nonzero exit, no shotplan written.
7. Write `out/shotplans/<UNIT>_shotplan.json`. Print a human-readable
   summary: card sequence with durations, total duration vs the lane's
   target band, gate pass/fail counts.
8. If `cfg.lane(unit.lane).get("human_script_review")`: print an explicit,
   visually distinct sign-off notice (e.g. a banner line) stating the script
   requires human review before `run` can proceed. `plan` never calls
   `render.render()` under any circumstance — that boundary belongs to
   `run`, not a config flag.

### `produce.py run --unit <ID>`

1. Require `out/shotplans/<UNIT>_shotplan.json` to exist. If missing, print
   a clear "run `plan --unit <ID>` first" message and return nonzero — no
   silent fallback to generating one inline.
2. `render.render(shotplan_path, draft_path)`.
3. Re-run `gates.brand.check(cfg, unit, shotlist)` against the shotplan that
   was actually rendered (loaded from the same file, not regenerated).
4. Determine the next version number by scanning
   `out/drafts/<UNIT>/<UNIT>_v*.mp4`, write to
   `out/drafts/<UNIT>/<UNIT>_v{N}.mp4` — never overwrites an existing file.
5. Print the exact output path and the brand gate's pass/fail result.

`run` does not call `tracker.update_status()` automatically in this pass —
that's a milestone-tracking decision (what counts as "drafted" vs
"approved") that touches a shared file outside this repo's exclusive
ownership, and belongs to a explicit follow-up once Sri has seen at least
one real draft. `tracker.py` is built and testable, but not auto-wired into
`run`'s happy path yet.

## Testing

Use BP34 (`03_Scripts_Out/BP3_T2_delete_me_the_bank_cannot_20260810_v1.csv`,
confirmed via `Unit_Index.xlsx`'s `csv_path` column for `unit_id == "BP34"`)
as the end-to-end proof case:

- `plan --unit BP34` warns on `ig_status == "not yet"`, does not block.
- Fidelity gate passes (verbatim CSV text can't drop BP34's own hedges).
- The shotplan's slide-3 and slide-8 scenes are `DiagramCard`s referencing
  `Erasure_Versus_Retention.svg` (confirmed present at
  `02_Vector_Library/T2_Intersections/`, not missing as the setup doc's
  stale §7 note suggested — resolved 18 Aug per the doc's own §9).
- Brand gate passes (amber only on the trap/regulator scene's hedge spans).
- `human_script_review: true` sign-off notice prints; `plan` does not
  attempt a render.
- `run --unit BP34` (invoked after the plan output is accepted) renders via
  Remotion, re-runs the brand gate, writes `out/drafts/BP34/BP34_v1.mp4`,
  prints the path and gate result.

## Open item carried forward, not decided here

Sri's voice-reference samples
(`assets/voice_reference/season_voice_sample.mp3`,
`blueprint_voice_sample.mp3`) raise a real question — audition against the
ElevenLabs Voice Library by ear, or upload for instant voice cloning via the
API — that has cost and licensing implications. This is explicitly Sri's
call, not to be decided by this build. It does not block `plan`/`run` since
`audio.py` doesn't exist yet; surfaced here so it isn't lost before Phase 3.
