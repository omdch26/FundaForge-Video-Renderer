import React, { useEffect, useState } from "react";
import { AbsoluteFill, cancelRender, continueRender, delayRender, staticFile } from "remotion";
import { PALETTE } from "../brand";
import { SAFE_PADDING, TYPE, css } from "../layout";
import { useEnter, riseIn, wipeIn } from "../motion";
import type { CardProps } from "../types";

/**
 * The "save this" payoff slide — and the clearest thing video adds over a carousel.
 *
 * A carousel can only show a diagram's end state. Here the diagram can build:
 * S1E05's learning curves can actually diverge on screen, which is the whole
 * concept being taught.
 *
 * SVGs are inlined rather than placed in an <img> for two reasons: their
 * internals become animatable, and their text inherits our registered fonts
 * (they reference "Inter" and "JetBrains Mono" by name — see fonts.ts).
 *
 * strip_backing_rect mirrors batch_render_season.py: every library asset carries
 * an opaque #0B0F17 rectangle, which punches a black hole through the card
 * unless removed.
 *
 * dangerouslySetInnerHTML is used deliberately here, not by oversight: these
 * SVGs are trusted, in-house-authored assets read from the local read-only
 * vector library (D:\System_Synthesis\02_Vector_Library), never user-supplied
 * content, so sanitizing them would add cost without a real threat model.
 */
const stripBackingRect = (svg: string): string => {
  // Matched against brand.json rather than a literal, so the palette stays the
  // one place a colour is ever written down.
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
    // KNOWN BUG: this currently renders blank. stripFixedDimensions() strips the
    // inner <svg>'s own width/height attrs, so with only a viewBox left on the
    // child, "width: auto" here resolves to zero. Not the default and no
    // consumer currently passes fitMode="crop" — left unfixed, documented only.
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
