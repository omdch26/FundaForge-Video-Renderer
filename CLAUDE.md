# CLAUDE.md — FundaForge Video Renderer

Instructions for any Claude session working in this repo. Read before writing code.

## WHAT THIS IS

A pipeline that turns finished FundaForge carousels into YouTube Shorts.
**Python orchestrates end to end. Remotion is the render engine, nothing more.**
No React is written per episode — the template is built once and frozen.

## THE SCOPE FENCE — NON-NEGOTIABLE

This repo lives inside `D:\System_Synthesis\06_Video_Production\`, which shares a
folder with the carousel production system so there is one source of truth.

### Read-only. Never write, never edit, never run.

| Path | What it is |
|---|---|
| `03_Scripts_Out/*.csv` | The 86 carousel scripts. **Input only.** |
| `03_Scripts_Out/batch_render_season.py` | Carousel renderer. Read for reference. Never run, never edit. |
| `05_Rendered_Carousels/` | 86 PDFs + PNG folders. Input only — and we render from CSV, not these. |
| `02_Vector_Library/` | Diagram SVGs. Read and reuse. Never edit. |
| `00_System_Context/`, `01_Backlog/` | Reference only. |
| `04_Brand_Assets/Fonts/` | Read and load. Never edit. |

### Writeable

`06_Video_Production/` only — which means this repo, and nothing above it.

**New diagrams for video, decided 18 Aug 2026:** the video lane is not a static
port of the carousel — it should be richer and more animated, video-native, not
a slide-by-slide copy. Where a script benefits from a diagram that doesn't
exist in `02_Vector_Library`, author a NEW one in `assets/diagrams/`. Rules,
none of them optional:
- Hand-coded vector SVG only — shapes, paths, text — same visual language as
  the existing library (see `02_Vector_Library/T1_Core_Concepts/Drift_Types_Three.svg`
  for the reference format). **Never** AI-generated/raster imagery — that ban
  is unchanged, see Imagery below.
- Never written into `02_Vector_Library` itself. New diagrams live only in
  `assets/diagrams/`, so the carousel's own source library is never touched.
- Must not disclose more than the source carousel slide already does. "Richer"
  means better animation and visual storytelling of the same claim — not new
  technical depth. **Unlike script text, there is no automated check for
  this** — `pipeline/gates/fidelity.py` only ever sees voiceover text
  (headline/body), never diagram content, so it cannot and does not enforce
  this boundary on a diagram. The boundary is enforced by human review alone,
  at the same shot-plan gate rule #4 below describes. If new diagrams become
  routine rather than rare, worth revisiting whether a cheap mechanical check
  (e.g. a required source-slide justification field) is worth adding — it
  still couldn't judge "does this show more," but it could at least catch an
  undocumented one.
- A proposed new diagram is part of the shot plan, not a silent render-time
  decision — Sri reviews what's proposed (what it shows, why no existing SVG
  covers it) at the same gate as the rest of the shot plan, before anything renders.

### When video work reveals a carousel problem

**Log it, do not fix it.** Append to `../Carousel_Feedback_Log.md` and tell Sri.
A carousel edit changes a rendered PDF that may already be scheduled.

## SAFETY RULES — ALWAYS

- **Never delete.** Superseded output moves to `out/<unit>/_superseded/`.
- **Never publish.** Upload is `private` only. Making a video public is a human action.
- **Never send.** No posting, no email, no external writes without explicit confirmation.
- Show Sri what you are about to do before doing any of the above.

## LOCKED DECISIONS — do not relitigate

| | |
|---|---|
| One short | One unit, all ten slides, one video |
| Source of truth | The CSV, via `Unit_Index.xlsx` -> `csv_path`. **Never the rendered PDF.** |
| Output | 1080x1920, 30fps, H.264 |
| Duration | Content-driven. Hard bounds 20-180s. Season target 45-75s, Blueprint 90-150s. |
| Voice | Two — one per lane. Voice ID and model ID pinned in config. |
| Music | Two beds — one per lane. Fixed gain ~-20dB under voice. |
| CTA | YouTube-only, three tiers. **No Instagram references anywhere.** |
| Imagery | **No AI-generated images.** Type-first, plus the SVG vector library. |
| Script generation | **SUPERSEDED 18 Aug 2026, same day.** Was deterministic/no-LLM; now full LLM-generated shot lists, decided after seeing that fixed-rule mapping can only copy-paste or hard-truncate CSV text, not intelligently compress or pace it. **The LLM is Claude, working interactively in the Cowork session — not an API call embedded in `script.py`.** Sri gives a unit ID in chat; Claude reads the CSV and `Unit_Index.xlsx` row directly, drafts the shot-list JSON against `schemas/shotlist.schema.json`, and writes it to `out/shotplans/<unit>_shotplan.json`. `script.py`/`produce.py plan` does NOT call an LLM API — its job is now to validate an already-authored shot plan (schema + `pipeline/gates/fidelity.py` + `pipeline/gates/humanization.py`) and report findings, not to generate one. No API key, no embedded model config, needed for this step. Because generation is no longer deterministic, the gates below are the ONLY technical safety net — not a backup to careful mapping. Do not weaken them, and do not let a shot plan skip them before rendering, for EITHER lane. |
| Fidelity gate scope | **Extended 18 Aug 2026 (fabrication check), then FIXED same day (per-slide hedge check).** Fabrication check added first — catches a new fact/number/example the source never had, warn-only. Testing it then exposed a real bug in the pre-existing hedge check: `HEDGE_DROPPED` compared hedge markers across the WHOLE script joined together, so one slide's flattened hedge hid behind any other slide that still hedged normally, and `TRAP_FLATTENED` only ever checked slide 9. Proven empirically: the committed bad fixture (slide 4 flattened, "retention wins" for "retention usually wins, narrowly") passed the entire gate suite under the old logic — exit_code 0 — because slides 2/5/8/10 still carried unrelated hedge language. Fixed by generalising the trap-only per-scene check (which was already correct in isolation) to run per slide, for all ten, not just slide 9. Regression-tested against both committed fixtures, wired into pytest for the first time (`test_full_bad_fixture_catches_hedge_dropped_per_slide`, `test_full_clean_fixture_passes_cleanly`). `ABSOLUTE_INTRODUCED` and `SLIDE_UNCOVERED` checked and confirmed NOT to share this blindspot — both are inherently global/per-slide by construction already. |
| Human script review | **Season flipped to mandatory, 18 Aug 2026.** Was `false` in `lanes.yaml` under the old deterministic approach, where nothing could be paraphrased wrong. Now both lanes generate via LLM, so both carry the same risk category. Set `season.human_script_review: true` to match `blueprint`. Revisit only once the gates have a real track record across enough real units. |
| Humanization | **Added 18 Aug 2026.** All on-screen/voiceover text is public-facing and must pass `00_System_Context/CLAUDE.md` Section XI (Humanization Standard) — no triplets, no inflated words (innovative/transformative/groundbreaking/leveraging/synergies), no artificial "it's not X, it's Y" parallelism, contractions used naturally, active voice. Concrete grounding for tone is `00_System_Context/Founder_Voice_Sample.md` (read-only reference, living document — re-read it each time, it grows). Before drafting any shot list, Claude reads both files. `pipeline/gates/humanization.py` (new, mirrors `fidelity.py`'s pattern-matching approach) checks the mechanical half of this — banned phrase list, triplet detection — deterministically; the "does it sound like Sri" half stays a judgement call made while drafting, same as it does for carousel copy. **This standard does not apply to operational docs** (this file, plans, trackers) — internal law is exempt, per Section XI.|
| `produce.py run` (Phase 4) | **Built 18 Aug 2026.** Renders an already-approved shot plan into a versioned draft. Re-runs the same gates `plan` uses (a plan can be hand-edited after approval — re-checking is cheap, a bad render isn't), then — for any lane with `human_script_review: true` — refuses to proceed unless called with `--confirmed`. Only then syncs that unit's diagram SVGs (resolved by filename against `02_Vector_Library`, never read from the stale `Asset_Register.md`), its lane's music bed, and its synthesized voiceover into `remotion/public/`, and shells out to `npx remotion render`. Never overwrites a previous draft — each attempt gets `out/drafts/<unit>/<unit>_v{N}.mp4`, incrementing. **Now also refuses to render a shot plan with no `audio.voice_file`** — added when Phase 3 landed, same day, because rendering against the author's guessed frame counts instead of the real recording would silently ship desynced cards/captions. **Not yet verified end-to-end**: real Remotion rendering needs platform-native `rspack` bindings, which neither this Cowork session's cloud sandbox nor the device bridge's Linux VM have (both are Linux; the repo's `node_modules` is Windows-built) — confirmed by direct attempt, same failure mode Sri anticipated for the original install issue. The Python orchestration (asset sync, versioning, gate + sign-off enforcement) is unit-tested and passes the full suite. The first real render must happen on Sri's own Windows machine, or via the VS Code session. |
| `produce.py audio` (Phase 3) | **Built 18 Aug 2026.** Real ElevenLabs voiceover, replacing the authored guess at pacing with the actual recording. Re-checks gates first (no point spending credits on a plan that would be rejected), then synthesizes ONE scene at a time — not one call for the whole script — so a hand-edit to one slide only re-spends on that slide; every clip is cached under `out/audio_cache/<unit>/` keyed by a hash of `(voice_id, model_id, tts_text)`, and `previous_text`/`next_text` are still passed to ElevenLabs on every call so prosody carries across the cut even though billing/caching is per-scene. Applies `config/pronunciation.json` to the TTS-bound text only — captions always show the original text (`GDPR`), never the spelled-out audio proxy (`G.D.P.R.`) — by construction: every substitution swaps exactly one whitespace token for exactly one other, so raw and TTS word lists stay index-aligned. Captions are built word-by-word from ElevenLabs' own character timestamps (never a transcriber — the whole shot list is already known text, see `cards/Captions.tsx`'s docstring), and a caption is marked `emphasis: "constraint"` only when its source word falls inside that scene's `amber_spans` — mirrors G2's amber-is-constraint-only rule so captions can never paint amber for punch alone. Scene `start_frame`/`duration_frames` are overwritten with the real speech boundaries (a card holding after its line ends, or cutting before it, is worse than disagreeing with the authored guess); a scene with no line (a pure visual beat) keeps its authored duration and just shifts to sit after whatever precedes it. Does **not** require `--confirmed` the way `run` does — synthesizing doesn't publish/send anything or introduce a new claim, it only speaks words already in the plan; `run` still gates on sign-off separately before it will render. New gate: `pipeline/gates/audio_gate.py` (G3) — `VOICE_ID_MISMATCH`/`MODEL_ID_MISMATCH` (fail) against the pinned lane config, `WPS_OUT_OF_RANGE` (warn, `config/pipeline.yaml` `audio.target_wps`), `CLIPPING` (fail, `pydub`-measured peak vs `audio.peak_ceiling_db`) — clipping is best-effort and downgrades to a warn if the file isn't synthesized yet or `pydub`/`ffmpeg` can't decode it on this machine, same reasoning as sync-fonts/Remotion needing the real machine. Wired into `validate_shotplan`/`plan` so it runs on every gate check, before and after audio exists. Fully unit-tested including a real (silent, `pydub`-generated) end-to-end retiming test — no real ElevenLabs calls anywhere in the test suite, and no live smoke test has been run from this session (no network reaches ElevenLabs from either this cloud sandbox in a way I'd spend Sri's credits without asking, or the device bridge's offline Linux VM). `.env`'s `ELEVENLABS_API_KEY` is confirmed present on the device; the first real synthesis call is Sri's or VS Code's to make. |
| `DiagramCard` animation | **Fixed 18 Aug 2026, while drafting S1E05.** `asset.animate` (`none`/`draw`/`reveal`/`scale_in`) has existed in the schema and `types.ts` since Phase 1 but was never read anywhere in `DiagramCard.tsx` — every diagram, regardless of its `animate` value, got the exact same whole-box fade/rise. Caught because S1E05 scene 4 ("watch the curves diverge") is the specific shot the pilot was chosen to prove out — see `Video_Pipeline_Setup_v1.0.md` §7 — and it would have shipped showing the *finished* curve fading in, not diverging on screen. Now wired up: `"draw"` wipes the diagram in left-to-right via clip-path (same mechanic as headline `wipeIn`) — deliberately not true per-path stroke-dasharray tracing, which needs each path's real rendered length via `getTotalLength()` and behaves inconsistently across filled shapes/text labels within a diagram; a left-to-right wipe works identically for any SVG and, for a left-to-right chart, reads as the line appearing over time anyway. `"scale_in"` pops up from slightly smaller while fading in (new `scaleIn` helper in `motion.ts`). `"reveal"`/`"none"` are unchanged — the original whole-box treatment, appropriate for a diagram doing a quick callback/recap rather than a first reveal. Typechecked clean (`tsc --noEmit` against the whole `remotion/src` tree, via a temporary local tsconfig — see next row) — not yet visually verified, since that needs a real render. |
| `remotion/` has no `tsconfig.json` | **Found 18 Aug 2026**, unrelated to anything I changed. `package.json`'s `"typecheck": "tsc --noEmit"` script currently does nothing useful — with no config file, `tsc` silently prints its own CLI help instead of checking anything, so a broken build could pass `npm run typecheck` today. Not fixed here — didn't want to hand-guess compiler options (target/module/moduleResolution/jsx) that belong to whoever owns the Remotion build, and got a real typecheck for this session's own change via a throwaway local config instead. Worth a real `tsconfig.json` before `typecheck` gets relied on for anything. |
| CTA verb: "Subscribe", not "Follow" | **Corrected 18 Aug 2026**, while drafting S1E05's CTA. "Follow" is Instagram/TikTok/X terminology — YouTube's actual mechanic is "Subscribe" (confirmed against YouTube's own Help Center; there is no separate "Follow" action on a regular YouTube channel). `Video_Pipeline_Setup_v1.0.md` §1's own CTA tier table used "follow" ("Stay on YouTube — follow, and the playlist auto-serves the next unit") and the Phase 1 demo shot list (`remotion/src/demo-shotlist.json`) copied that same word — both predate this fix and are the reason the wrong verb made it into S1E05's first draft too. Tier-1 CTA copy is now "Subscribe" (+ "turn on notifications", per Sri's request — the standard two-part YouTube CTA; the bell is a notification-preference toggle layered on a subscription, not a second follow-equivalent). Fixed in S1E05's shot plan; **not yet swept through `demo-shotlist.json` or `Video_Pipeline_Setup_v1.0.md`** — those are reference/planning artifacts, not render inputs for a real unit, so left alone unless Sri wants them corrected too. Any future unit's CTA should say "Subscribe", never "Follow". |
| Shorts format, confirmed 18 Aug 2026 | 1080×1920 (9:16) and the 20–180s duration bounds already in `config/pipeline.yaml` both check out against YouTube's current rules: Shorts classification needs a square-or-vertical aspect ratio (9:16 is the recommended one, not the only one) and now allows up to 3 minutes (extended from 60s on 15 Oct 2024 — still current). No #Shorts tag is required for classification; that's a discovery-signal nice-to-have for Phase 6 metadata, not a rendering requirement. Subscribe/notification-bell mechanics are identical for Shorts and long-form — nothing platform-specific to build for. |

## BRAND — LOCKED UPSTREAM

Single source of truth: `config/brand.json`. Python and Remotion both read it.
**Never hardcode a colour or font name anywhere else.**

- Obsidian `#0B0F17`, slate `#1E293B`, white `#F8FAFC`, cyan `#06B6D4`, amber `#F59E0B`, muted `#64748B`
- **Amber means constraint, warning, trap, failure mode. Never decoration.** This is enforced by a gate.
- **Cyan for Seasons, amber for Blueprints.** Always.
- Fonts: Space Grotesk (headlines), Inter (body), Fira Code (episode badge + lane label),
  JetBrains Mono (**inside SVG diagrams only**).
- Banned: stock photos, AI-generated images, motivational quotes, headshots.

### Font gotcha

The Inter files register as `Inter 24pt`, not `Inter`. Built SVGs reference plain `Inter`.
Register **both** names in Remotion or diagram text silently falls back.

## THE COMMERCIAL BOUNDARY — THE RULE THAT MATTERS MOST

Curriculum Modules 11 and 12 are a paid B2B product. Free content gives the **what** and
the **why**. It never gives the **how** or the **evidence**.

**Compression is where this breaks.** A carousel spends three slides establishing that a
problem has no clean resolution; a short is tempted to state a flat rule — and that flat
rule is exactly the position the carousel deliberately withheld.

**When compressing: cut breadth, never cut the caveat.**

This is enforced by `pipeline/gates/fidelity.py`. Do not weaken it.

## CODE STANDARDS

- Layered: `source -> script -> gates -> audio -> assets -> shotlist -> render -> meta`.
  Each stage reads and writes files under `out/<unit_id>/`. No stage reaches past its neighbours.
- Every stage is **idempotent and resumable** — if its output exists and the source hash
  matches, skip it.
- Comments explain **why**, not what.
- The Python/Remotion contract is `schemas/shotlist.schema.json`. Validate against it on
  both sides. Changing the schema means changing both.
