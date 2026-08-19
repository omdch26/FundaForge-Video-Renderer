import React from "react";
import { interpolate, useCurrentFrame } from "remotion";
import { PALETTE } from "../brand";
import { SAFE } from "../layout";
import { EASE_OUT } from "../motion";

/**
 * Per Sri (19 Aug 2026, third "more movement" round): an explicit, named
 * exception to motion.ts's "no mascot" call — for this one pictorial element
 * only, in the bottom-right corner, for the full length of every video.
 *
 * Still inside CLAUDE.md's real rule: no AI-GENERATED imagery, not "no
 * imagery" — both shapes below are hand-authored vector shapes (rects/paths,
 * the same primitives FundaForgeMark is built from), animated with plain
 * frame maths, exactly like everything else in this file tree. And the
 * motion itself still obeys "no bounce, no overshoot" — EASE_OUT throughout,
 * nothing springy — Sri's exception was for ADDING a pictorial motif, not for
 * loosening how things move once added.
 *
 * Positioning: first draft sat flush with the true frame corner, which meant
 * it could dip under YouTube's own Shorts chrome (the like/comment/share
 * rail down the right, the title/handle bar along the bottom — see
 * layout.ts's SAFE docstring). Sri asked to shift it inward so it always
 * stays fully clear instead — CORNER_INSET below anchors the item's own
 * outer edge to the SAFE box's edge (plus a small buffer), not to the true
 * frame edge, so it never crosses into that reserved zone regardless of
 * lane or content.
 */
const CORNER_SIZE = 152;
const CORNER_INSET_BUFFER = 12; // a little inside the safe line itself, not just flush to it
const CORNER_RIGHT = SAFE.right + CORNER_INSET_BUFFER;
const CORNER_BOTTOM = SAFE.bottom + CORNER_INSET_BUFFER;

/**
 * Season — a pencil that never stops scratching a line across the corner.
 * The dash pattern flows by an ever-increasing offset (never a bounded
 * interpolate that resets), so there's no visible "restart" seam — it just
 * keeps writing. The pencil itself jitters at two incommensurate frame
 * periods (11 & 17) so the hand-writing motion doesn't read as a robotic
 * identical loop within a typical 45-90s short.
 */
export const PencilScribble: React.FC<{ accent: string }> = ({ accent }) => {
  const frame = useCurrentFrame();

  const dashOffset = -(frame * 3.2);
  const jitterX = Math.sin((frame / 11) * Math.PI * 2) * 3;
  const jitterY = Math.cos((frame / 17) * Math.PI * 2) * 2;
  const tilt = -40 + Math.sin((frame / 13) * Math.PI * 2) * 3;

  return (
    <div style={{ position: "absolute", right: CORNER_RIGHT, bottom: CORNER_BOTTOM,
                  width: CORNER_SIZE, height: CORNER_SIZE, pointerEvents: "none" }}>
      <svg viewBox="0 0 160 160" width={CORNER_SIZE} height={CORNER_SIZE} style={{ overflow: "visible" }}>
        {/* the line the pencil is continuously writing */}
        <path
          d="M14 122 Q 38 98 60 120 T 104 120 T 140 96"
          fill="none" stroke={accent} strokeWidth={5} strokeLinecap="round"
          strokeDasharray="9 9" strokeDashoffset={dashOffset} opacity={0.85}
        />
        {/* pencil, tip riding near the leading end of the line */}
        <g transform={`translate(${130 + jitterX} ${82 + jitterY}) rotate(${tilt})`}>
          <rect x="-7" y="-50" width="14" height="46" rx="2" fill={PALETTE.fog} />
          <rect x="-7" y="-50" width="14" height="10" rx="2" fill={accent} />
          <path d="M-7 -4L7 -4L0 12Z" fill={PALETTE.white} />
          <path d="M-2 -4L2 -4L0 4Z" fill={PALETTE.obsidian} />
        </g>
      </svg>
    </div>
  );
};

const FOLD_LOOP = 96; // frames per open -> hold -> close -> hold cycle

/**
 * Blueprint — a document folder whose cover continuously folds open and
 * shut, hinged at the top, revealing a document inside. Real CSS 3D
 * (rotateX), rendered natively by Chromium at capture time — no DOM
 * measurement, fully deterministic from `frame` alone, same as every other
 * animated value in this codebase.
 */
export const FolderUnfold: React.FC<{ accent: string }> = ({ accent }) => {
  const frame = useCurrentFrame();
  const t = frame % FOLD_LOOP;

  let openness: number;
  if (t < 30) {
    openness = interpolate(t, [0, 30], [0, 1], { extrapolateRight: "clamp", easing: EASE_OUT });
  } else if (t < 50) {
    openness = 1;
  } else if (t < 80) {
    openness = interpolate(t, [50, 80], [1, 0], { extrapolateRight: "clamp", easing: EASE_OUT });
  } else {
    openness = 0;
  }

  const flapAngle = -openness * 150;
  const docLift = interpolate(openness, [0, 1], [0, -8]);
  const docOpacity = interpolate(openness, [0.25, 1], [0, 1], {
    extrapolateLeft: "clamp", extrapolateRight: "clamp",
  });

  const W = CORNER_SIZE;
  const H = CORNER_SIZE;
  const bodyW = W * 0.76;
  const bodyH = H * 0.6;
  const bodyLeft = (W - bodyW) / 2;
  const bodyTop = H * 0.32;

  return (
    <div style={{ position: "absolute", right: CORNER_RIGHT, bottom: CORNER_BOTTOM,
                  width: W, height: H, pointerEvents: "none", perspective: 480 }}>
      {/* folder back / pocket */}
      <div style={{ position: "absolute", left: bodyLeft, top: bodyTop, width: bodyW, height: bodyH,
                    borderRadius: 8, background: PALETTE.slate, border: `2px solid ${accent}` }} />

      {/* document, revealed as the cover lifts */}
      <div style={{ position: "absolute", left: bodyLeft + bodyW * 0.12, top: bodyTop + docLift,
                    width: bodyW * 0.76, opacity: docOpacity }}>
        <div style={{ height: 5, background: accent, opacity: 0.8, marginBottom: 7, borderRadius: 2 }} />
        <div style={{ height: 5, width: "78%", background: PALETTE.fog, opacity: 0.6, marginBottom: 7, borderRadius: 2 }} />
        <div style={{ height: 5, width: "60%", background: PALETTE.fog, opacity: 0.6, borderRadius: 2 }} />
      </div>

      {/* front cover, hinged at the top, folding back to reveal the document */}
      <div style={{ position: "absolute", left: bodyLeft, top: bodyTop, width: bodyW, height: bodyH * 0.72,
                    borderRadius: "8px 8px 0 0", background: accent,
                    transformOrigin: "top center", transform: `rotateX(${flapAngle}deg)`,
                    transformStyle: "preserve-3d" }}>
        <div style={{ position: "absolute", top: -12, left: bodyW * 0.28, width: bodyW * 0.3, height: 12,
                      borderRadius: "4px 4px 0 0", background: accent }} />
      </div>
    </div>
  );
};
