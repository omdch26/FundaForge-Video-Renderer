# Remotion bring-up: get the render pipeline actually working

**Date:** 2026-08-18
**Status:** Approved

## Context

A prior cloud-sandbox session produced draft Remotion source under `remotion/`
(`Root.tsx`, `Short.tsx`, five card components, `fonts.ts`, `brand.ts`,
`layout.ts`, `motion.ts`, `types.ts`, `demo-shotlist.json`, `sync-fonts.mjs`)
but never got it installed or rendering, and fell back to a broken hand-coded
workaround. That workaround is not present in this repo — what's here is only
the untested draft.

Inspection confirms:
- The draft is well-designed and already matches CLAUDE.md's locked decisions
  (brand tokens sourced from `config/brand.json`, safe-area insets, the
  Inter/`Inter 24pt` double-registration, amber-is-a-signal enforcement via
  `AmberText`, schema-mirrored `types.ts`).
- `remotion/node_modules` does not exist — `npm install` has never been run.
- No `.env` exists — `sync-fonts.mjs` requires `SYSTEM_ROOT` and will hard-fail
  without it.
- Nothing in this repo is committed to git yet (`main` has no commits).
- The diagram card component has no real fit-mode logic for the 824x420
  landscape SVGs against a 1080x1920 frame — it relies on incidental sizing
  inside a padded flex container, not a deliberate scale/crop/letterbox
  decision.

So the bulk of the work is **verification that the existing design actually
runs**, not a rewrite. The one real gap is the diagram card's aspect-ratio
handling.

## Goal

Get a real Remotion render working end to end in this repo, using the
existing draft components, and fix the diagram card so it deliberately
handles the 824x420-in-1080x1920 mismatch instead of accidentally fitting.

## Non-goals

- Rewriting any card component from scratch.
- Touching the Python pipeline (`pipeline/`, `produce.py`) or the gates.
- Generating new SVGs — diagrams are read from `02_Vector_Library` by filename
  only, never authored here.
- Picking the diagram fit mode unilaterally — render all three, let the user
  choose from stills.

## Approach

### 1. Install & prove the toolchain works
- Copy `.env.example` to `.env`, set `SYSTEM_ROOT=D:/System_Synthesis`.
- `npm install` in `remotion/`.
- `npm run sync-fonts` — confirms the brand TTFs copy from
  `04_Brand_Assets/Fonts` into `remotion/public/fonts`, and fails loud (per
  the script's existing exit-1 behavior) if any are missing.
- Confirm `npx remotion --version` resolves and Chromium launches (headless
  render smoke test).
- Render the existing `demo-shotlist.json` composition (`Short`) end-to-end
  before changing any card. This is the existing "default composition" for
  this repo — there's no separate scaffold-default to fall back to, since we
  are not re-scaffolding with `create-video`.

### 2. Prove fonts load, don't assume it
- `fonts.ts::registerFonts()` already exists and looks correct (including the
  Inter/`Inter 24pt` alias fix documented in its own comment). Add a
  console.log per font-face rule registered, so the render log shows which
  families were injected.
- Add a temporary on-frame diagnostic (e.g. a small swatch row rendering each
  registered family name in that family) to one test composition, render a
  still, and eyeball it — remove before the final verification render.
- Confirm the inlined SVG's plain `font-family="Inter, sans-serif"` and
  `"JetBrains Mono, monospace"` resolve against the registered font-face
  rules. The diagram card component inlines the SVG as real DOM inside the
  Remotion tree — verify on a rendered still rather than assume CSS cascade
  behavior, since this is explicitly an open, unverified question on the
  carousel side too.

### 3. Stress-test text layout with real copy
- Pull body/headline text from a real carousel CSV in `03_Scripts_Out/`
  (e.g. `BP2_T2_bronze_silver_gold_what_changes_20260810_v1.csv`, which has
  body text up to ~180 characters, longer than the current demo shotlist).
- Swap this into a test shotlist for BodyCard and TrapCard.
- Confirm existing flexbox layout (`maxWidth: 820`, `line-height` from
  `layout.ts::TYPE`) holds without clipping inside the safe area at this
  length. Fix only if it doesn't — no preemptive layout changes.

### 4. Fix the diagram card's fit-mode handling
Build three variants of the scaling logic, each behind a quick prop/flag for
comparison purposes only (not a shipped runtime option unless one is chosen):
- **(a) Letterbox** — scale SVG to fit container width, obsidian
  (`PALETTE.obsidian`) fill above/below inside the slate card.
- **(b) Crop** — scale to fit height, overflow hidden, losing left/right
  edges.
- **(c) Bleed** — scale to fit width, no letterbox fill; the existing slate
  card background and padding provide the frame instead.

Render one still of each against `02_Vector_Library/T1_Core_Concepts/Drift_Types_Three.svg`
(chosen because it's confirmed to exist and its markup is already known —
smallest label text is `font-size="9"` at the SVG's native 824px width).
Compute what that 9px becomes in rendered pixels at each option's final
scale, and report legibility honestly from the still — don't guess.

Present the three stills; do not pick one without sign-off.

### 5. Render and verify
- Build a 4-scene test shotlist: TitleCard (Hook), BodyCard, TrapCard (using
  the CSV-sourced longer copy from step 3), DiagramCard (using the fit mode
  chosen in step 4).
- Render to mp4.
- Extract 4-5 stills via `ffmpeg -ss` and inspect each for: no text clipping,
  brand fonts (not a fallback) actually rendering, colors matching
  `config/brand.json` hex values exactly, safe-area margins respected, and
  diagram label legibility.

## Testing

Verification is the deliverable here — there's no separate test suite step.
Success is: a real mp4 exists in `out/`, its extracted stills show correct
fonts/colors/layout, and the diagram card's chosen fit mode is confirmed
legible on a phone-scale still.

## Open questions resolved during brainstorming

- Existing draft code: keep as scaffold, verify and fix rather than
  re-scaffolding with `create-video`.
- Diagram fit mode: build and show all three options as rendered stills;
  user picks after seeing them.
