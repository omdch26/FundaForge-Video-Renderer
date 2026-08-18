import React from "react";
import { AbsoluteFill, useCurrentFrame } from "remotion";
import { PALETTE } from "../brand";
import { SAFE, TYPE, css } from "../layout";
import type { Caption } from "../types";

/**
 * Word-level captions, timed from ElevenLabs character timestamps.
 *
 * NOT from Whisper. We wrote the script, so we already know every word — running
 * our own TTS back through a transcriber would only introduce errors on
 * technical terms and British spellings ("minimising" -> "minimizing"), and lose
 * information we started with.
 *
 * emphasis "constraint" renders amber and is gate-restricted to constraint,
 * warning, trap and failure-mode words. Never plain emphasis — a draft pipeline
 * was caught painting amber onto "NOT" and "EXACT" purely for punch, which
 * destroys the signal.
 *
 * Sits above the bottom safe area so YouTube's title and handle never cover it.
 */
const WINDOW = 3; // words on screen at once — enough to read, few enough to track

export const Captions: React.FC<{ captions: Caption[]; accent: string }> = ({ captions, accent }) => {
  const frame = useCurrentFrame();

  const idx = captions.findIndex((c) => frame >= c.start_frame && frame <= c.end_frame);
  if (idx === -1) return null;

  const start = Math.floor(idx / WINDOW) * WINDOW;
  const group = captions.slice(start, start + WINDOW);

  return (
    <AbsoluteFill style={{ justifyContent: "flex-end", alignItems: "center",
                           paddingBottom: SAFE.bottom + 40, paddingLeft: 60, paddingRight: 60 }}>
      <div style={{ display: "flex", gap: 18, flexWrap: "wrap", justifyContent: "center" }}>
        {group.map((c, i) => {
          const active = start + i === idx;
          const colour =
            c.emphasis === "constraint" ? PALETTE.amber
            : c.emphasis === "accent" ? accent
            : PALETTE.white;
          return (
            <span key={`${c.start_frame}-${i}`} style={{
              ...css(TYPE.caption),
              color: colour,
              opacity: active ? 1 : 0.38,
              transition: "none",
            }}>
              {c.text}
            </span>
          );
        })}
      </div>
    </AbsoluteFill>
  );
};
