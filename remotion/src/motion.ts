import { Easing, interpolate, useCurrentFrame } from "remotion";

/**
 * Motion vocabulary for the whole system, in one place.
 *
 * The brand is austere and type-led, so motion is restrained by design: short
 * ease-out moves, no bounce, no overshoot on body content. Anything springy
 * would read as consumer-app rather than technical reference.
 *
 * The one exception is amber. Constraint and trap elements SNAP in slightly
 * faster and harder, because amber is a signal and it should feel like one.
 */

export const EASE_OUT = Easing.bezier(0.16, 1, 0.3, 1);
export const EASE_SNAP = Easing.bezier(0.34, 1.2, 0.4, 1);

/** 0 -> 1 over `duration` frames, beginning at `delay`. */
export const useEnter = (delay = 0, duration = 14, easing = EASE_OUT): number => {
  const frame = useCurrentFrame();
  return interpolate(frame, [delay, delay + duration], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing,
  });
};

/** Rise and fade — the default entrance for type. */
export const riseIn = (p: number, distance = 28) => ({
  opacity: p,
  transform: `translateY(${(1 - p) * distance}px)`,
});

/** Wipe from the left. Used for headlines, where a rise feels too soft. */
export const wipeIn = (p: number) => ({
  clipPath: `inset(0 ${(1 - p) * 100}% 0 0)`,
  opacity: p < 0.02 ? 0 : 1,
});

/** Amber's harder entrance. */
export const snapIn = (p: number) => ({
  opacity: p,
  transform: `scale(${0.94 + p * 0.06})`,
});

/** Scale up from slightly smaller, fading in — a diagram's "pop" entrance,
 * distinct from riseIn's plain drift-up-and-fade. `from` is the starting
 * scale; smaller values read as more of a pop, closer to 1 reads subtler. */
export const scaleIn = (p: number, from = 0.88) => ({
  opacity: p,
  transform: `scale(${from + p * (1 - from)})`,
});

/** A rule that draws itself. Used under headlines and beside trap cards. */
export const drawRule = (p: number, vertical = false) =>
  vertical ? { transform: `scaleY(${p})`, transformOrigin: "top" }
           : { transform: `scaleX(${p})`, transformOrigin: "left" };

/**
 * Fade out over the last `frames` of a scene, so cuts breathe rather than snap.
 * Deliberately subtle — a hard cut on a 45s short is fine, a visible crossfade is not.
 */
export const useExit = (durationInFrames: number, frames = 8): number => {
  const frame = useCurrentFrame();
  return interpolate(frame, [durationInFrames - frames, durationInFrames], [1, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: EASE_OUT,
  });
};

/** Stagger helper: nth element enters `step` frames after the first. */
export const stagger = (n: number, step = 5) => n * step;

/**
 * Per Sri (19 Aug 2026): "more movement, more catchy" for the Shorts, without
 * a mascot/character (ruled out — collides with the "no bounce, no overshoot"
 * rule above, and with the no-AI-imagery ban if it were ever generated rather
 * than hand-drawn). These two helpers are the toolkit for the alternative
 * that was agreed instead: more motion from the EXISTING restrained
 * vocabulary — continuous, low-amplitude, sine-based "breathing" rather than
 * anything springy — applied to accents, glows and captions, never to body
 * copy itself.
 */

/** A smooth, continuous oscillation — for an idle "breathing" glow/pulse on
 * an accent element, never on body text. Deliberately sine-based (no ease
 * curve, no settle point) so it reads as ambient life, not an entrance. */
export const usePulse = (period = 90, amplitude = 0.15, base = 0.35, phaseFrames = 0): number => {
  const frame = useCurrentFrame();
  return base + amplitude * Math.sin(((frame + phaseFrames) / period) * Math.PI * 2);
};

/** Appends an alpha channel to a 6-digit brand hex colour (e.g. from
 * PALETTE), for glows/shadows that need to fade in and out with usePulse.
 * Chromium (Remotion's render target) supports 8-digit #RRGGBBAA. */
export const withAlpha = (hex: string, alpha: number): string => {
  const a = Math.round(Math.max(0, Math.min(1, alpha)) * 255).toString(16).padStart(2, "0");
  return `${hex}${a}`;
};
