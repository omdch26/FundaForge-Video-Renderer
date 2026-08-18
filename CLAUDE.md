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
  technical depth. This is the same boundary `pipeline/gates/fidelity.py`
  enforces on script text; a new diagram is held to it too.
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
| Fidelity gate scope | **Extended 18 Aug 2026.** `pipeline/gates/fidelity.py`'s existing checks (hedge preservation, absolute introduction, trap-slide integrity, hook verbatim) catch *flattening* — a real claim stated too strongly. They do not catch *fabrication* — a new fact, number, or example the source never had, since nothing about it matches a flattening pattern. Add a check for this: flag any generated sentence containing a number, statistic, named example, or specific claim that doesn't trace back to the unit's own CSV text. Needed now specifically because generation is fully open-ended, not template-filling. |
| Human script review | **Season flipped to mandatory, 18 Aug 2026.** Was `false` in `lanes.yaml` under the old deterministic approach, where nothing could be paraphrased wrong. Now both lanes generate via LLM, so both carry the same risk category. Set `season.human_script_review: true` to match `blueprint`. Revisit only once the gates have a real track record across enough real units. |
| Humanization | **Added 18 Aug 2026.** All on-screen/voiceover text is public-facing and must pass `00_System_Context/CLAUDE.md` Section XI (Humanization Standard) — no triplets, no inflated words (innovative/transformative/groundbreaking/leveraging/synergies), no artificial "it's not X, it's Y" parallelism, contractions used naturally, active voice. Concrete grounding for tone is `00_System_Context/Founder_Voice_Sample.md` (read-only reference, living document — re-read it each time, it grows). Before drafting any shot list, Claude reads both files. `pipeline/gates/humanization.py` (new, mirrors `fidelity.py`'s pattern-matching approach) checks the mechanical half of this — banned phrase list, triplet detection — deterministically; the "does it sound like Sri" half stays a judgement call made while drafting, same as it does for carousel copy. **This standard does not apply to operational docs** (this file, plans, trackers) — internal law is exempt, per Section XI.|

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
