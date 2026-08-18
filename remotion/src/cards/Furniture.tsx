import React from "react";
import { AbsoluteFill, interpolate, useCurrentFrame } from "remotion";
import { PALETTE } from "../brand";
import { SAFE, TYPE, css } from "../layout";
import { EASE_OUT } from "../motion";

/**
 * Episode badge, series kicker, wordmark — present on every frame.
 *
 * A short must be unmistakably one lane or the other within a second of landing,
 * with no context and no channel page. The kicker plus the accent rule is what
 * does that work.
 */
export const Furniture: React.FC<{
  kicker: string; unitId: string; accent: string; lane: string;
}> = ({ kicker, unitId, accent }) => {
  const frame = useCurrentFrame();
  const enter = interpolate(frame, [0, 20], [0, 1], {
    extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: EASE_OUT,
  });

  return (
    <AbsoluteFill style={{ pointerEvents: "none", opacity: enter }}>
      <div style={{ position: "absolute", top: SAFE.top - 110, left: SAFE.left }}>
        <div style={{ display: "flex", alignItems: "center", gap: 14 }}>
          <div style={{ width: 3, height: 26, background: accent }} />
          <span style={{ ...css(TYPE.badge), color: PALETTE.white }}>{unitId}</span>
        </div>
        <div style={{ ...css(TYPE.kicker), color: accent, opacity: 0.8,
                      letterSpacing: 2.4, marginTop: 8, marginLeft: 17 }}>
          {kicker}
        </div>
      </div>

      <div style={{ position: "absolute", bottom: SAFE.bottom - 120, left: SAFE.left,
                    fontFamily: "Space Grotesk", fontWeight: 500, fontSize: 26,
                    color: PALETTE.white, opacity: 0.45 }}>
        FundaForge
      </div>
    </AbsoluteFill>
  );
};
