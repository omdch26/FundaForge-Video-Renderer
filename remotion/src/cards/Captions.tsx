import React from "react";
import { AbsoluteFill, interpolate, useCurrentFrame } from "remotion";
import { PALETTE } from "../brand";
import { SAFE, TYPE, css } from "../layout";
import { EASE_OUT, EASE_SNAP, scaleIn } from "../motion";
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
 * Default (non-emphasis) word colour is `fog`, not `white` — captions are a
 * supporting read-along layer, not on-screen copy, and using the same white as
 * the card's own headline/body made the two illegible at a glance (Sri, 18 Aug
 * 2026, after the first real render). `fog` is deliberately desaturated: enough
 * contrast from the card's white text to read as a distinct layer, not vivid
 * enough to compete with amber/accent emphasis. Muted (not-yet-spoken) words
 * dim via opacity exactly as before — that fade-from-grey-to-lit read-along
 * effect is intentional and unchanged.
 *
 * Sits above the bottom safe area so YouTube's title and handle never cover it.
 *
 * Per Sri (19 Aug 2026, "more movement" request — see motion.ts's usePulse
 * docstring for the fuller context): each word now pops in with a short
 * scale-up the instant it becomes active, instead of just an opacity fade.
 * Captions are the one element on screen every single frame of every video,
 * so this is the highest-visibility place to add kinetic energy without
 * touching a card's own body copy. Amber/constraint words get the same
 * harder EASE_SNAP pop TrapCard's label already uses — reusing the one
 * sanctioned overshoot exception, not inventing a new one. The pop is brief
 * (5-7 frames) and settles to a static scale well before the word's spoken
 * duration ends, so it reads as a landing, not a wobble.
 */
const WINDOW = 3; // words on screen at once — enough to read, few enough to track
const POP_DURATION_NORMAL = 7;
const POP_DURATION_HARD = 5;

export const Captions: React.FC<{ captions: Caption[]; accent: string }> = ({ captions, accent }) => {
  const frame = useCurrentFrame();

  const idx = captions.findIndex((c) => frame >= c.start_frame && frame <= c.end_frame);
  if (idx === -1) return null;

  const start = Math.floor(idx / WINDOW) * WINDOW;
  const group = captions.slice(start, start + WINDOW);

  return (
    <AbsoluteFill style={{ justifyContent: "flex-end", alignItems: "center",
                           paddingBottom: SAFE.bottom + 40, paddingLeft: 60, paddingRight: 60 }}>
      <div style={{ display: "flex", gap: 14, flexWrap: "wrap", justifyContent: "center" }}>
        {group.map((c, i) => {
          const active = start + i === idx;
          const hard = c.emphasis === "constraint";
          const colour =
            c.emphasis === "constraint" ? PALETTE.amber
            : c.emphasis === "accent" ? accent
            : PALETTE.fog;

          const popDuration = hard ? POP_DURATION_HARD : POP_DURATION_NORMAL;
          const popProgress = active
            ? interpolate(frame, [c.start_frame, c.start_frame + popDuration], [0, 1], {
                extrapolateLeft: "clamp", extrapolateRight: "clamp",
                easing: hard ? EASE_SNAP : EASE_OUT,
              })
            : 1; // not this word's moment — no pop, just sits at rest scale

          const pop = active ? scaleIn(popProgress, hard ? 0.78 : 0.9) : { transform: "scale(1)" };

          return (
            <span key={`${c.start_frame}-${i}`} style={{
              ...css(TYPE.caption),
              color: colour,
              opacity: active ? 1 : 0.38,
              display: "inline-block",
              transform: pop.transform,
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
