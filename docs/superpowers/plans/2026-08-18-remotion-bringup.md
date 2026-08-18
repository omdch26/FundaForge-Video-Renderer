# Remotion Bring-Up Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Get the existing draft Remotion renderer in `remotion/` actually installed and rendering end to end, fix the diagram card's aspect-ratio handling for 824x420 SVGs in a 1080x1920 frame, and produce a verified test render with stills proving fonts/colors/layout/legibility are correct.

**Architecture:** No new components except a bounded fix to `DiagramCard.tsx`'s scaling logic and a temporary font-diagnostic composition. Everything else is toolchain bring-up (install, env, font sync) and verification (render + extract stills + inspect). Python pipeline is untouched.

**Tech Stack:** Remotion 4.x, React 18, TypeScript, Node 24 (already installed, exceeds the 18+ floor), ffmpeg (already installed at `/c/yt-dlp/ffmpeg`) for still extraction.

## Global Constraints

- Never edit anything under `03_Scripts_Out/`, `05_Rendered_Carousels/`, `02_Vector_Library/`, `00_System_Context/`, `01_Backlog/`, `04_Brand_Assets/Fonts/` — read-only, per CLAUDE.md.
- Writeable scope is `06_Video_Production/FundaForge-Video-Renderer/` only.
- Output is 1080x1920, 30fps, H.264.
- Brand colors/fonts come only from `config/brand.json` — never hardcode a hex or font family name elsewhere.
- No AI-generated images; diagrams are existing SVGs read from `02_Vector_Library` by filename, never authored here.
- No Instagram references, no comment-keyword CTAs — YouTube-only, three CTA tiers.
- `.env` is gitignored — never commit it.
- Diagram card must not pick a fit mode unilaterally — render all three options and get sign-off before finalizing.

---

### Task 1: Environment setup and dependency install

**Files:**
- Create: `.env` (repo root, copied from `.env.example`)
- Modify: none

**Interfaces:**
- Produces: a working `node_modules` under `remotion/`, and `SYSTEM_ROOT` available to `remotion/scripts/sync-fonts.mjs` via `.env`.

- [ ] **Step 1: Copy `.env.example` to `.env` and fill in `SYSTEM_ROOT`**

```bash
cd "d:\System_Synthesis\06_Video_Production\FundaForge-Video-Renderer"
cp .env.example .env
```

Edit `.env` and set:
```
SYSTEM_ROOT=D:/System_Synthesis
```
Leave `ELEVENLABS_API_KEY`, `ANTHROPIC_API_KEY`, `GEMINI_API_KEY`, `YOUTUBE_CLIENT_SECRET_PATH` blank — not needed for this bring-up.

- [ ] **Step 2: Install npm dependencies**

```bash
cd "d:\System_Synthesis\06_Video_Production\FundaForge-Video-Renderer\remotion"
npm install
```

Expected: completes without error, creates `remotion/node_modules/`.

- [ ] **Step 3: Verify the Remotion CLI resolves**

```bash
npx remotion --version
```

Expected: prints a version string (4.x). If this fails with "could not determine executable to run" (the error seen before `node_modules` existed), stop and diagnose — do not proceed to create-video re-scaffolding per the approved design; instead check `package.json`'s `@remotion/cli` version and confirm `node_modules/.bin/remotion` exists.

- [ ] **Step 4: Run font sync and confirm all files copy**

```bash
npm run sync-fonts
```

Expected output: `fonts: 7/7 copied from D:/System_Synthesis/04_Brand_Assets/Fonts`. If any are missing, the script exits 1 and lists them — do not proceed until this is 7/7.

- [ ] **Step 5: No commit for this task**

`.env` is gitignored and `node_modules` is gitignored. This task only proves the environment works; move to Task 2.

---

### Task 2: Render the existing demo composition end to end

**Files:**
- Modify: none (this task only proves the existing `Short` composition renders)

**Interfaces:**
- Consumes: `remotion/src/index.ts` -> `RemotionRoot` -> `Short` composition, `remotion/src/demo-shotlist.json` as default props.
- Produces: `out/_phase1_dummy.mp4`, proving the full toolchain (Chromium launch, font files present, TypeScript compiles) works.

- [ ] **Step 1: Typecheck first**

```bash
cd "d:\System_Synthesis\06_Video_Production\FundaForge-Video-Renderer\remotion"
npm run typecheck
```

Expected: no errors. If there are errors, fix them before attempting a render (a render failure on top of a typecheck failure makes diagnosis harder).

- [ ] **Step 2: Render the demo composition**

```bash
npm run dummy
```

This runs `sync-fonts` again (idempotent) then `remotion render src/index.ts Short ../out/_phase1_dummy.mp4`.

- [ ] **Step 3: If it fails with a Chromium/browser launch error**

On Windows this is less common than on Linux (no `libnss3`/`libgbm1` issue), but if you see an error like "Could not find Chromium" or a browser launch failure:

```bash
npx remotion browser ensure
```

This downloads Remotion's pinned Chromium build. Re-run `npm run dummy` after.

- [ ] **Step 4: Confirm the output file exists and has a sane size**

```bash
ls -la "d:\System_Synthesis\06_Video_Production\FundaForge-Video-Renderer\out\_phase1_dummy.mp4"
```

Expected: file exists, size > 100KB (a 20s 1080x1920 H.264 clip should be well above this; a near-zero-byte file means the render silently failed).

- [ ] **Step 5: No commit**

`out/` is gitignored. This task is a verification checkpoint; proceed to Task 3 only if Steps 2-4 succeeded.

---

### Task 3: Prove fonts actually load (not a silent fallback)

**Files:**
- Modify: `remotion/src/fonts.ts` (add console logging per registered face)
- Create: `remotion/src/FontDiagnostic.tsx` (temporary composition, deleted at the end of this task)
- Modify: `remotion/src/Root.tsx` (temporarily add the diagnostic composition, removed at the end of this task)

**Interfaces:**
- Consumes: `PALETTE` from `remotion/src/brand.ts`.
- Produces: nothing persisted — this task's only artifact is a rendered still proving fonts resolve, and a permanent one-line-per-face console log left in `fonts.ts`.

- [ ] **Step 1: Add console logging to `registerFonts()`**

Edit `remotion/src/fonts.ts`. Change the `face` helper to log each registration:

```typescript
export const registerFonts = (): void => {
  const face = (family: string, file: string, weight = 400) => {
    console.log(`[fonts] registering "${family}" (weight ${weight}) from ${file}`);
    return `
    @font-face {
      font-family: "${family}";
      src: url("${staticFile(`fonts/${file}`)}") format("truetype");
      font-weight: ${weight};
      font-display: block;
    }`;
  };

  const css = [
    face("Space Grotesk", "SpaceGrotesk-Medium.ttf", 500),
    face("Space Grotesk", "SpaceGrotesk-Bold.ttf", 700),
    face("Inter", "Inter_24pt-Regular.ttf"),
    face("Inter 24pt", "Inter_24pt-Regular.ttf"), // alias — see docstring
    face("Fira Code", "FiraCode-Regular.ttf"),
    face("Fira Code", "FiraCode-Bold.ttf", 700),
    face("JetBrains Mono", "JetBrainsMono-Regular.ttf"),
    face("JetBrains Mono", "JetBrainsMono-Bold.ttf", 700),
  ].join("\n");

  const el = document.createElement("style");
  el.textContent = css;
  document.head.appendChild(el);
  console.log(`[fonts] ${css.split("@font-face").length - 1} font-face rules injected`);
};
```

- [ ] **Step 2: Create a temporary diagnostic composition**

Create `remotion/src/FontDiagnostic.tsx`:

```tsx
import React, { useEffect } from "react";
import { AbsoluteFill } from "remotion";
import { PALETTE } from "./brand";
import { registerFonts } from "./fonts";

const SAMPLE_MARKUP = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 400 60" width="400" height="60">
  <text x="10" y="25" font-family="Inter, sans-serif" font-size="18" fill="#F8FAFC">Inter via SVG</text>
  <text x="10" y="50" font-family="JetBrains Mono, monospace" font-size="14" fill="#F8FAFC">JetBrains Mono via SVG</text>
</svg>`;

const ROWS: { label: string; family: string }[] = [
  { label: "Space Grotesk 700", family: "Space Grotesk" },
  { label: "Inter (plain)", family: "Inter" },
  { label: "Inter 24pt (alias)", family: "Inter 24pt" },
  { label: "Fira Code", family: "Fira Code" },
  { label: "JetBrains Mono", family: "JetBrains Mono" },
];

export const FontDiagnostic: React.FC = () => {
  useEffect(() => { registerFonts(); }, []);

  return (
    <AbsoluteFill style={{ backgroundColor: PALETTE.obsidian, padding: 60 }}>
      {ROWS.map((r) => (
        <div key={r.family} style={{ marginBottom: 24 }}>
          <div style={{ color: PALETTE.muted, fontSize: 16, fontFamily: "monospace" }}>{r.label}</div>
          <div style={{ color: PALETTE.white, fontSize: 36, fontFamily: r.family, fontWeight: 700 }}>
            The quick brown fox — 0123456789
          </div>
        </div>
      ))}
      <div style={{ marginTop: 24 }}>
        <div style={{ color: PALETTE.muted, fontSize: 16, fontFamily: "monospace" }}>
          Inlined markup (tests plain "Inter"/"JetBrains Mono" cascade)
        </div>
        <div
          // The library's diagram SVGs are trusted, in-house-authored assets read
          // from the local read-only vector folder — not user-supplied content —
          // so inlining here mirrors DiagramCard's own established pattern.
          dangerouslySetInnerHTML={{ __html: SAMPLE_MARKUP }}
        />
      </div>
    </AbsoluteFill>
  );
};
```

- [ ] **Step 3: Temporarily register the diagnostic composition**

Edit `remotion/src/Root.tsx` — add a second `<Composition>` for the diagnostic. Insert after the existing `Short` composition, inside a fragment:

```tsx
import React from "react";
import { Composition } from "remotion";
import { Short } from "./Short";
import { FontDiagnostic } from "./FontDiagnostic";
import demo from "./demo-shotlist.json";
import type { Shotlist } from "./types";

export const RemotionRoot: React.FC = () => (
  <>
    <Composition
      id="Short"
      component={Short as never}
      durationInFrames={(demo as unknown as Shotlist).duration_frames}
      fps={30}
      width={1080}
      height={1920}
      defaultProps={demo as never}
      calculateMetadata={({ props }) => ({
        durationInFrames: (props as Shotlist).duration_frames,
        fps: (props as Shotlist).fps,
      })}
    />
    <Composition
      id="FontDiagnostic"
      component={FontDiagnostic}
      durationInFrames={30}
      fps={30}
      width={1080}
      height={1920}
    />
  </>
);
```

- [ ] **Step 4: Render the diagnostic and check the console log**

```bash
cd "d:\System_Synthesis\06_Video_Production\FundaForge-Video-Renderer\remotion"
npx remotion render src/index.ts FontDiagnostic ../out/_font_diagnostic.mp4 2>&1 | tee /tmp/font_render.log
```

Confirm the log contains 8 `[fonts] registering ...` lines and the `X font-face rules injected` line. If any registration line is missing, that font failed to load before continuing.

- [ ] **Step 5: Extract a still and eyeball it**

```bash
ffmpeg -y -ss 00:00:00.5 -i "d:\System_Synthesis\06_Video_Production\FundaForge-Video-Renderer\out\_font_diagnostic.mp4" -frames:v 1 "d:\System_Synthesis\06_Video_Production\FundaForge-Video-Renderer\out\_font_diagnostic_still.png"
```

Read the resulting PNG (via the Read tool, which supports images) and confirm: each row visibly uses a distinct typeface (Space Grotesk's geometric look, Inter's humanist body font, Fira Code/JetBrains Mono's monospace look) — not five rows that all look like the same system fallback font. Confirm the inlined markup's two lines also render in their named fonts, not a generic sans-serif fallback.

Report the finding plainly: if the markup's plain `"Inter"` / `"JetBrains Mono"` names do NOT resolve to the registered faces (i.e. they look like Arial/system default instead of matching the labeled rows above them), state that clearly — this answers the open question from the design doc and determines whether `DiagramCard` needs an explicit `fontFamily` override injected into its SVG string rather than relying on cascade.

- [ ] **Step 6: Clean up the temporary diagnostic**

Revert `remotion/src/Root.tsx` to its original single-composition form (remove the `FontDiagnostic` import and second `<Composition>`, remove the fragment wrapper if no longer needed). Delete `remotion/src/FontDiagnostic.tsx`. Keep the `console.log` additions in `fonts.ts` — those are permanent, low-cost diagnostics.

- [ ] **Step 7: Typecheck and commit**

```bash
cd "d:\System_Synthesis\06_Video_Production\FundaForge-Video-Renderer\remotion"
npm run typecheck
cd ..
git add remotion/src/fonts.ts remotion/src/Root.tsx
git status
```

Confirm `FontDiagnostic.tsx` does NOT appear in `git status` (it was deleted, never committed). Then:

```bash
git commit -m "$(cat <<'EOF'
Add font registration logging; verify brand fonts load, not fallback

Confirmed via a temporary diagnostic composition (rendered, inspected,
removed) that all 8 font-face rules register and render distinctly,
including the Inter/JetBrains Mono names as referenced by inlined
library diagrams.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 4: Stress-test card text layout with real carousel copy

**Files:**
- Create: `remotion/src/test-shotlist-longcopy.json`
- Modify: none in `src/cards/` unless Step 5 finds an actual problem

**Interfaces:**
- Consumes: `Shotlist` type from `remotion/src/types.ts`, existing `TitleCard`/`BodyCard`/`TrapCard` components — no code changes expected unless clipping is found.
- Produces: `out/_longcopy_test.mp4` and stills proving layout holds at realistic text length.

- [ ] **Step 1: Build a test shotlist using real CSV copy**

Create `remotion/src/test-shotlist-longcopy.json`. Pull headline/body strings from `03_Scripts_Out/BP2_T2_bronze_silver_gold_what_changes_20260810_v1.csv` (rows 5 and 9 — among the longest body strings):

```json
{
  "unit_id": "BP02",
  "lane": "blueprint",
  "series": "Blueprint",
  "kicker": "DATA ARCHITECTURE \u00b7 PRODUCTION DEPTH",
  "accent": "#F59E0B",
  "fps": 30,
  "width": 1080,
  "height": 1920,
  "duration_frames": 450,
  "audio": { "voice_file": null, "music_file": null, "music_gain_db": -20 },
  "scenes": [
    {
      "scene_id": 1,
      "card": "BodyCard",
      "start_frame": 0,
      "duration_frames": 180,
      "slide_refs": [5],
      "headline": "Silver is where the meaning is fixed.",
      "body": "Types enforced, duplicates removed, entities conformed, quality gates applied. A model reading silver may assume shape, but not agreement."
    },
    {
      "scene_id": 2,
      "card": "TrapCard",
      "start_frame": 180,
      "duration_frames": 270,
      "slide_refs": [9],
      "headline": "Which layer is your model reading?",
      "body": "Then: what does that layer guarantee, and what are you checking yourself. Teams that cannot answer the second half are trusting a promise nobody made.",
      "amber_spans": [
        { "field": "body", "start": 0, "end": 27, "reason": "regulator_question" }
      ]
    }
  ],
  "cta": { "tier": 1, "on_screen": "FOLLOW FOR THE NEXT ONE", "next_unit": null }
}
```

- [ ] **Step 2: Render it**

```bash
cd "d:\System_Synthesis\06_Video_Production\FundaForge-Video-Renderer\remotion"
npx remotion render src/index.ts Short ../out/_longcopy_test.mp4 --props=src/test-shotlist-longcopy.json
```

- [ ] **Step 3: Extract stills at the midpoint of each scene**

```bash
ffmpeg -y -ss 00:00:03 -i "d:\System_Synthesis\06_Video_Production\FundaForge-Video-Renderer\out\_longcopy_test.mp4" -frames:v 1 "d:\System_Synthesis\06_Video_Production\FundaForge-Video-Renderer\out\_longcopy_scene1.png"
ffmpeg -y -ss 00:00:07 -i "d:\System_Synthesis\06_Video_Production\FundaForge-Video-Renderer\out\_longcopy_test.mp4" -frames:v 1 "d:\System_Synthesis\06_Video_Production\FundaForge-Video-Renderer\out\_longcopy_scene2.png"
```

- [ ] **Step 4: Inspect both stills**

Read both PNGs. Confirm: body text wraps within `maxWidth: 820`, does not overflow the safe area (`SAFE = { top: 220, bottom: 420, left: 72, right: 160 }` from `layout.ts`), and no line is clipped at the frame edge. Confirm the amber span on the TrapCard body ("Which layer..." — first 27 chars) renders in `PALETTE.amber`, not white.

- [ ] **Step 5: If clipping is found**

Only if Step 4 reveals actual overflow: adjust `TYPE.body.size` or `maxWidth` in `remotion/src/layout.ts`, re-render, re-check. Do not make speculative changes if Step 4 shows no problem — this task is verification-first.

- [ ] **Step 6: Commit the test shotlist**

```bash
cd "d:\System_Synthesis\06_Video_Production\FundaForge-Video-Renderer"
git add remotion/src/test-shotlist-longcopy.json
git status
```

If Step 5 required a `layout.ts` change, add that file too. Then:

```bash
git commit -m "$(cat <<'EOF'
Verify card layout holds against real carousel-length copy

Stress-tested BodyCard and TrapCard with body text pulled from an
actual Blueprint CSV (~180 chars) rather than the shorter demo
shotlist copy. Confirmed no clipping within the safe area.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 5: Fix DiagramCard fit-mode handling — build all three options

**Files:**
- Modify: `remotion/src/cards/DiagramCard.tsx`
- Create: `remotion/src/test-shotlist-diagram.json`
- Create: `remotion/public/diagrams/Drift_Types_Three.svg` (copy, not edit, of the read-only library asset)

**Interfaces:**
- Consumes: `CardProps` from `types.ts` (unchanged), `PALETTE` from `brand.ts`.
- Produces: `DiagramCard` accepts an optional `fitMode?: "letterbox" | "crop" | "bleed"` prop for this comparison.

- [ ] **Step 1: Rewrite DiagramCard with explicit fit-mode scaling**

The current component renders the SVG at intrinsic size inside a padded flex container with no deliberate scale logic. Replace the render body with one that applies one of three container strategies. Edit `remotion/src/cards/DiagramCard.tsx`:

```tsx
import React, { useEffect, useState } from "react";
import { AbsoluteFill, cancelRender, continueRender, delayRender, staticFile } from "remotion";
import { PALETTE } from "../brand";
import { SAFE_PADDING, TYPE, css } from "../layout";
import { useEnter, riseIn, wipeIn } from "../motion";
import type { CardProps } from "../types";

const stripBackingRect = (svg: string): string => {
  const bg = PALETTE.obsidian.replace("#", "");
  const rect = new RegExp(`<rect\\b[^>]*fill=["']#${bg}["'][^>]*/>`, "gi");
  return svg.replace(rect, "");
};

// The inlined markup carries its own explicit width/height attributes, which
// override a CSS width:100% on the outer wrapper in some browsers. Stripping
// them (viewBox is untouched, so aspect ratio is preserved) lets our own
// container control the final scale.
const stripFixedDimensions = (svg: string): string =>
  svg.replace(/(<svg\b[^>]*)\swidth="\d+"\s+height="\d+"/, "$1");

// The library's diagrams are all 824x420 (landscape, ~1.96:1), built for a
// 4:5 carousel slide. A 9:16 frame needs a deliberate fit strategy — this was
// previously implicit (intrinsic size inside a flex container), which is why
// it's called out explicitly here rather than left to chance.
type FitMode = "letterbox" | "crop" | "bleed";

const SOURCE_ASPECT = 824 / 420;

const containerStyleFor = (mode: FitMode): React.CSSProperties => {
  const base: React.CSSProperties = {
    marginTop: 48,
    background: PALETTE.slate,
    borderRadius: 20,
    overflow: "hidden",
    width: "100%",
    position: "relative",
  };
  if (mode === "letterbox") {
    // Fit width; obsidian fill shows above/below the SVG's own aspect ratio.
    return { ...base, aspectRatio: `${SOURCE_ASPECT}`, backgroundColor: PALETTE.obsidian };
  }
  if (mode === "crop") {
    // Fit a taller target box; overflow hidden crops left/right edges.
    return { ...base, aspectRatio: "3 / 4" };
  }
  // bleed: fit width exactly to the SVG's own ratio, card padding is the only frame.
  return { ...base, aspectRatio: `${SOURCE_ASPECT}` };
};

const svgWrapperStyleFor = (mode: FitMode): React.CSSProperties => {
  if (mode === "crop") {
    // Scale so the SVG's height fills the taller 3:4 box, center-crop the width.
    return { width: "auto", height: "100%", position: "absolute", left: "50%", transform: "translateX(-50%)" };
  }
  return { width: "100%", height: "100%" };
};

export const DiagramCard: React.FC<CardProps & { fitMode?: FitMode }> = ({
  headline, asset, accent, fitMode = "letterbox",
}) => {
  const [svg, setSvg] = useState<string | null>(null);
  const [handle] = useState(() => delayRender("Loading diagram SVG"));

  const head = useEnter(0, 14);
  const fig = useEnter(8, 22);

  useEffect(() => {
    if (!asset?.path) {
      continueRender(handle);
      return;
    }
    fetch(staticFile(asset.path))
      .then((r) => r.text())
      .then((text) => {
        const stripped = asset.strip_backing_rect === false ? text : stripBackingRect(text);
        setSvg(stripFixedDimensions(stripped));
        continueRender(handle);
      })
      .catch((e) => cancelRender(e));
  }, [asset?.path, asset?.strip_backing_rect, handle]);

  return (
    <AbsoluteFill style={{ padding: SAFE_PADDING, justifyContent: "center" }}>
      {headline ? (
        <h2 style={{ ...css(TYPE.headline), color: PALETTE.white, ...wipeIn(head) }}>
          {headline}
        </h2>
      ) : null}

      <div
        style={{
          ...containerStyleFor(fitMode),
          borderLeft: fitMode === "bleed" ? `4px solid ${accent}` : undefined,
          ...riseIn(fig, 24),
        }}
      >
        {svg ? (
          <div
            style={svgWrapperStyleFor(fitMode)}
            // Library diagrams are trusted, in-house-authored assets read from
            // the local read-only vector folder, matching the original
            // component's own established pattern for this card.
            dangerouslySetInnerHTML={{ __html: svg }}
          />
        ) : (
          <div style={{ ...css(TYPE.body), color: PALETTE.muted, padding: 36 }}>
            [diagram unavailable — rendering type-only]
          </div>
        )}
      </div>
    </AbsoluteFill>
  );
};
```

- [ ] **Step 2: Copy the confirmed diagram asset into Remotion's public dir**

`02_Vector_Library` is outside Remotion's `public/`, so `staticFile()` can't resolve it directly — mirrors how `sync-fonts.mjs` copies fonts into `public/fonts`. This is a one-off manual copy for this verification task (the real pipeline's asset-sync step is out of scope for this plan):

```bash
mkdir -p "d:\System_Synthesis\06_Video_Production\FundaForge-Video-Renderer\remotion\public\diagrams"
cp "d:\System_Synthesis\02_Vector_Library\T1_Core_Concepts\Drift_Types_Three.svg" "d:\System_Synthesis\06_Video_Production\FundaForge-Video-Renderer\remotion\public\diagrams\Drift_Types_Three.svg"
```

- [ ] **Step 3: Build a test shotlist referencing the confirmed SVG**

Create `remotion/src/test-shotlist-diagram.json`:

```json
{
  "unit_id": "T1_TEST",
  "lane": "season",
  "series": "Season 1",
  "kicker": "MACHINE LEARNING \u00b7 INTERVIEW FOUNDATIONS",
  "accent": "#06B6D4",
  "fps": 30,
  "width": 1080,
  "height": 1920,
  "duration_frames": 90,
  "audio": { "voice_file": null, "music_file": null, "music_gain_db": -20 },
  "scenes": [
    {
      "scene_id": 1,
      "card": "DiagramCard",
      "start_frame": 0,
      "duration_frames": 90,
      "slide_refs": [4],
      "headline": "Three kinds of drift.",
      "asset": {
        "kind": "svg_library",
        "path": "diagrams/Drift_Types_Three.svg",
        "strip_backing_rect": true
      }
    }
  ],
  "cta": { "tier": 1, "on_screen": "FOLLOW FOR THE NEXT ONE", "next_unit": null }
}
```

- [ ] **Step 4: Render all three fit modes**

`fitMode` isn't a schema field (comparison-only), so render three times by temporarily editing `DiagramCard.tsx`'s default parameter for each pass.

```bash
cd "d:\System_Synthesis\06_Video_Production\FundaForge-Video-Renderer\remotion"
```

For `letterbox` (already the default from Step 1):
```bash
npx remotion render src/index.ts Short ../out/_diagram_letterbox.mp4 --props=src/test-shotlist-diagram.json
```

Edit `DiagramCard.tsx`: change `fitMode = "letterbox"` to `fitMode = "crop"`, then:
```bash
npx remotion render src/index.ts Short ../out/_diagram_crop.mp4 --props=src/test-shotlist-diagram.json
```

Change to `fitMode = "bleed"`, then:
```bash
npx remotion render src/index.ts Short ../out/_diagram_bleed.mp4 --props=src/test-shotlist-diagram.json
```

Set the default back to `fitMode = "letterbox"` when done (recommended starting default — safest, no content loss).

- [ ] **Step 5: Extract a still from each and compute label legibility**

```bash
ffmpeg -y -ss 00:00:02 -i "d:\System_Synthesis\06_Video_Production\FundaForge-Video-Renderer\out\_diagram_letterbox.mp4" -frames:v 1 "d:\System_Synthesis\06_Video_Production\FundaForge-Video-Renderer\out\_diagram_letterbox_still.png"
ffmpeg -y -ss 00:00:02 -i "d:\System_Synthesis\06_Video_Production\FundaForge-Video-Renderer\out\_diagram_crop.mp4" -frames:v 1 "d:\System_Synthesis\06_Video_Production\FundaForge-Video-Renderer\out\_diagram_crop_still.png"
ffmpeg -y -ss 00:00:02 -i "d:\System_Synthesis\06_Video_Production\FundaForge-Video-Renderer\out\_diagram_bleed.mp4" -frames:v 1 "d:\System_Synthesis\06_Video_Production\FundaForge-Video-Renderer\out\_diagram_bleed_still.png"
```

Compute the scale factor for each mode:
- Letterbox: container width = `1080 - 72 - 160 = 848px`. SVG scales to fill that width at its native 824:420 ratio, so scale factor = `848 / 824 ≈ 1.029x`. The 9px source label becomes `9 * 1.029 ≈ 9.3px` rendered.
- Crop: container is `848px` wide × `848 * 4/3 ≈ 1131px` tall. SVG scales to fill height: `1131 / 420 ≈ 2.69x`. The 9px label becomes `9 * 2.69 ≈ 24.2px` rendered — but roughly `(824 * 2.69 - 848) / 2 ≈ 685px` of width is cropped off each side, likely losing the leftmost/rightmost diagram panels entirely on this 3-panel diagram.
- Bleed: identical scale to letterbox (`≈1.029x`) since it's also fit-to-width — the only difference is the absence of obsidian letterbox fill; legibility is the same as letterbox.

- [ ] **Step 6: Read all three stills and report legibility honestly**

Read each PNG. For each, state plainly whether the smallest label text (the `font-size="9"` captions like "VISIBLE TODAY · NO LABELS NEEDED") is legible at that still's actual rendered scale — don't rely on the computed number alone, since font hinting and anti-aliasing affect real legibility differently than the math suggests. Flag if crop mode has visibly cut off content (expected, given the panel layout is wider than a 3:4 box can hold without cropping two of the three drift-type panels).

This is a decision checkpoint — do not proceed to Task 6 until the user has seen the three stills and picked a fit mode.

- [ ] **Step 7: Set the chosen fit mode as the permanent default**

Once the user picks, edit `DiagramCard.tsx`'s default parameter to match (e.g. `fitMode = "letterbox"`). Ask the user whether to keep all three modes as a `fitMode` prop for future per-diagram flexibility, or simplify to just the winning mode (delete unused branches). Default recommendation if not asked: keep the `fitMode` prop in the component but do not add it to `types.ts`/`schemas/shotlist.schema.json` yet — YAGNI until a real diagram needs a different mode.

- [ ] **Step 8: Typecheck and commit**

```bash
cd "d:\System_Synthesis\06_Video_Production\FundaForge-Video-Renderer\remotion"
npm run typecheck
cd ..
git add remotion/src/cards/DiagramCard.tsx remotion/src/test-shotlist-diagram.json remotion/public/diagrams/Drift_Types_Three.svg
git status
git commit -m "$(cat <<'EOF'
Give DiagramCard deliberate fit-mode scaling for 824x420 SVGs

Previously relied on intrinsic SVG sizing inside a padded flex
container, with no real scale decision. Built and compared letterbox,
crop, and bleed against Drift_Types_Three.svg; letterbox chosen as the
default — crop loses two of three panels on this diagram's layout, and
bleed offers no legibility advantage over letterbox.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 6: Full 4-card render and final verification

**Files:**
- Create: `remotion/src/test-shotlist-full.json`

**Interfaces:**
- Consumes: all five card components, the chosen `fitMode` default from Task 5.
- Produces: `out/_full_verification.mp4` and 4 stills — the final deliverable proving the pipeline works end to end.

- [ ] **Step 1: Build a 4-scene test shotlist**

Create `remotion/src/test-shotlist-full.json`, combining TitleCard, BodyCard, DiagramCard (asset from Task 5), and TrapCard (long-copy content from Task 4):

```json
{
  "unit_id": "BP02",
  "lane": "blueprint",
  "series": "Blueprint",
  "kicker": "DATA ARCHITECTURE \u00b7 PRODUCTION DEPTH",
  "accent": "#F59E0B",
  "fps": 30,
  "width": 1080,
  "height": 1920,
  "duration_frames": 570,
  "audio": { "voice_file": null, "music_file": null, "music_gain_db": -20 },
  "scenes": [
    {
      "scene_id": 1,
      "card": "TitleCard",
      "start_frame": 0,
      "duration_frames": 120,
      "slide_refs": [1],
      "headline": "Which layer is your model reading?",
      "body": "Bronze, silver, gold. Three layers everyone can name and few can defend."
    },
    {
      "scene_id": 2,
      "card": "BodyCard",
      "start_frame": 120,
      "duration_frames": 150,
      "slide_refs": [5],
      "headline": "Silver is where the meaning is fixed.",
      "body": "Types enforced, duplicates removed, entities conformed, quality gates applied. A model reading silver may assume shape, but not agreement."
    },
    {
      "scene_id": 3,
      "card": "DiagramCard",
      "start_frame": 270,
      "duration_frames": 120,
      "slide_refs": [4],
      "headline": "Three kinds of drift.",
      "asset": {
        "kind": "svg_library",
        "path": "diagrams/Drift_Types_Three.svg",
        "strip_backing_rect": true
      }
    },
    {
      "scene_id": 4,
      "card": "TrapCard",
      "start_frame": 390,
      "duration_frames": 180,
      "slide_refs": [9],
      "headline": "Which layer is your model reading?",
      "body": "Then: what does that layer guarantee, and what are you checking yourself. Teams that cannot answer the second half are trusting a promise nobody made.",
      "amber_spans": [
        { "field": "body", "start": 0, "end": 27, "reason": "regulator_question" }
      ]
    }
  ],
  "cta": { "tier": 1, "on_screen": "FOLLOW FOR THE NEXT ONE", "next_unit": null }
}
```

- [ ] **Step 2: Render**

```bash
cd "d:\System_Synthesis\06_Video_Production\FundaForge-Video-Renderer\remotion"
npx remotion render src/index.ts Short ../out/_full_verification.mp4 --props=src/test-shotlist-full.json
```

- [ ] **Step 3: Extract one still per scene**

```bash
ffmpeg -y -ss 00:00:02 -i "d:\System_Synthesis\06_Video_Production\FundaForge-Video-Renderer\out\_full_verification.mp4" -frames:v 1 "d:\System_Synthesis\06_Video_Production\FundaForge-Video-Renderer\out\_full_scene1_title.png"
ffmpeg -y -ss 00:00:05 -i "d:\System_Synthesis\06_Video_Production\FundaForge-Video-Renderer\out\_full_verification.mp4" -frames:v 1 "d:\System_Synthesis\06_Video_Production\FundaForge-Video-Renderer\out\_full_scene2_body.png"
ffmpeg -y -ss 00:00:10 -i "d:\System_Synthesis\06_Video_Production\FundaForge-Video-Renderer\out\_full_verification.mp4" -frames:v 1 "d:\System_Synthesis\06_Video_Production\FundaForge-Video-Renderer\out\_full_scene3_diagram.png"
ffmpeg -y -ss 00:00:14 -i "d:\System_Synthesis\06_Video_Production\FundaForge-Video-Renderer\out\_full_verification.mp4" -frames:v 1 "d:\System_Synthesis\06_Video_Production\FundaForge-Video-Renderer\out\_full_scene4_trap.png"
```

- [ ] **Step 4: Inspect all four stills against the checklist**

Read each PNG and confirm, per still:
- No text clipped at frame edges or safe-area boundary.
- Headline font is Space Grotesk (geometric, distinct from Inter body text) — not a system fallback.
- Body font is Inter — not a system fallback.
- Colors match `config/brand.json` exactly: obsidian `#0B0F17` background, amber `#F59E0B` only on TrapCard's flagged span and its lane-label/rule elements, accent `#F59E0B` (blueprint lane) on TitleCard's rule and Furniture.
- Furniture (episode badge, kicker, "FundaForge" wordmark) sits inside the safe area, not covered or clipped.
- DiagramCard's diagram is legible per the fit mode chosen in Task 5.

Report the check results plainly — pass/fail per item, not a blanket "looks good."

- [ ] **Step 5: Commit the final test shotlist**

```bash
cd "d:\System_Synthesis\06_Video_Production\FundaForge-Video-Renderer"
git add remotion/src/test-shotlist-full.json
git commit -m "$(cat <<'EOF'
Add 4-card end-to-end verification shotlist

Combines TitleCard, BodyCard, DiagramCard, and TrapCard with real
carousel-derived copy and the confirmed diagram asset. Rendered and
visually verified: fonts, brand colors, safe-area margins, and
diagram legibility all confirmed correct on extracted stills.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

## Post-plan note

Test shotlists (`test-shotlist-*.json`) and their renders in `out/` are
verification artifacts, not production shotlists — the real pipeline
generates `shotlist.json` per unit via the Python side
(`pipeline/` -> `schemas/shotlist.schema.json`), untouched by this plan.
Leave the test JSON files in `remotion/src/` as regression fixtures for
future Remotion-side changes; they cost nothing to keep and give the next
session something to re-render if a card component changes.
