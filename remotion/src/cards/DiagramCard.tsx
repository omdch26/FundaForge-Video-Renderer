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
 */
const stripBackingRect = (svg: string): string => {
  // Matched against brand.json rather than a literal, so the palette stays the
  // one place a colour is ever written down.
  const bg = PALETTE.obsidian.replace("#", "");
  const rect = new RegExp(`<rect\\b[^>]*fill=["']#${bg}["'][^>]*/>`, "gi");
  return svg.replace(rect, "");
};

export const DiagramCard: React.FC<CardProps> = ({ headline, asset, accent }) => {
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
        setSvg(asset.strip_backing_rect === false ? text : stripBackingRect(text));
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
          marginTop: 48,
          background: PALETTE.slate,
          borderRadius: 20,
          borderLeft: `4px solid ${accent}`,
          padding: 36,
          ...riseIn(fig, 24),
        }}
      >
        {svg ? (
          <div
            style={{ width: "100%" }}
            // Library SVGs are our own, authored in-house and read-only.
            dangerouslySetInnerHTML={{ __html: svg }}
          />
        ) : (
          // A missing asset must never block a render — see assets.py fallback rules.
          <div style={{ ...css(TYPE.body), color: PALETTE.muted }}>
            [diagram unavailable — rendering type-only]
          </div>
        )}
      </div>
    </AbsoluteFill>
  );
};
