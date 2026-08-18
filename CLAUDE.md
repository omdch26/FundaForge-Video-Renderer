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
