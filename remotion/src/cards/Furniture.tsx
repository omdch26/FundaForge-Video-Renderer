import React, { useMemo } from "react";
import { AbsoluteFill, interpolate, useCurrentFrame } from "remotion";
import { PALETTE } from "../brand";
import { SAFE, TYPE, css } from "../layout";
import { EASE_OUT, EASE_SNAP, withAlpha } from "../motion";
import type { Scene } from "../types";

const FRAME_WIDTH = 1080; // matches <Composition width> in Root.tsx — shorts are a fixed 9:16 canvas
const ICON_SIZE = 110;
const ICON_GAP = 8;
const KICKER_MAX_SIZE = 29;
const KICKER_MIN_SIZE = 18;
const KICKER_LETTER_SPACING = 2.4;

let measureCanvas: HTMLCanvasElement | null = null;

/**
 * Shrinks the kicker to fit one line instead of wrapping. Season's kicker is
 * short enough to always sit at the full 29px; Blueprint's arc/domain/theme
 * triplet can run long enough to wrap onto a second line on the narrow 9:16
 * frame even though it fits fine on the wider carousel slide. Measured with
 * an actual canvas context rather than a guessed char-width ratio, since
 * Fira Code Bold's real advance width is what's loaded at render time —
 * guessing a ratio here would drift from whatever font actually resolves.
 */
const fitKickerFontSize = (text: string, maxWidth: number): number => {
  if (typeof document === "undefined") return KICKER_MAX_SIZE;
  if (!measureCanvas) measureCanvas = document.createElement("canvas");
  const ctx = measureCanvas.getContext("2d");
  if (!ctx) return KICKER_MAX_SIZE;
  const widthAt = (size: number) => {
    ctx.font = `700 ${size}px "Fira Code"`;
    return ctx.measureText(text).width + (text.length - 1) * KICKER_LETTER_SPACING;
  };
  let size = KICKER_MAX_SIZE;
  while (size > KICKER_MIN_SIZE && widthAt(size) > maxWidth) size -= 1;
  return size;
};

/**
 * Per Sri (19 Aug 2026, "more movement" follow-up): four bespoke beats for
 * the corner mark, one each at the video's open, every diagram payoff, the
 * trap, and the close — landed instead of a mascot (see motion.ts's usePulse
 * docstring for that decision). Every beat is built from the same two
 * ingredients Sri asked for: the amber/cyan "leaf" (the middle-arrow path)
 * doing a quick swish IN PLACE — a translateX nudge and back, never a
 * reposition of the badge itself — plus a brief glow sourced from the leaf's
 * own colour. No new shapes, no rotation, no scale distortion of the mark.
 *
 * Each function below takes `t` = frames since ITS OWN trigger point (not
 * the absolute video frame) and returns the two values FundaForgeMark needs.
 * Deliberately four separate named functions rather than one parameterised
 * generic — Sri asked for "one separate action for each frame unique to it,"
 * and keeping them syntactically distinct makes it obvious at a glance that
 * each was actually tuned for its moment, not stamped from a shared template.
 */
type IconAction = { leafX: number; glow: number };
const REST_ACTION: IconAction = { leafX: 0, glow: 0 };

/** Triangle envelope helper (0 -> 1 -> 0) shared by the single-swish beats
 * below — NOT exported, and deliberately not a public part of the motion
 * vocabulary: this is Furniture's own internal shape, not a general-purpose
 * primitive like motion.ts's helpers. */
const swish = (t: number, duration: number, distance: number, glowPeak: number, easing = EASE_OUT): IconAction => {
  const half = duration / 2;
  const p = t <= half
    ? interpolate(t, [0, half], [0, 1], { extrapolateRight: "clamp", easing })
    : interpolate(t, [half, duration], [1, 0], { extrapolateRight: "clamp", easing });
  return { leafX: distance * p, glow: glowPeak * p };
};

const TITLE_ARRIVE_DURATION = 22;
/** Open — the mark itself "arrives" alongside the opening hook, a calm
 * single swish rather than just fading in flat with everything else. */
const titleArriveAction = (t: number): IconAction =>
  swish(t, TITLE_ARRIVE_DURATION, 6, 0.4, EASE_OUT);

const DIAGRAM_POINT_DURATION = 16;
/** Each diagram's payoff — a crisper, slightly larger swish, like the mark
 * is pointing at what just landed. Re-triggers at every DiagramCard scene,
 * not just the first. */
const diagramPointAction = (t: number): IconAction =>
  swish(t, DIAGRAM_POINT_DURATION, 8, 0.5, EASE_OUT);

const TRAP_ALERT_DURATION = 12;
/** The trap/regulator's-question beat — fast and sharp, EASE_SNAP (the one
 * sanctioned overshoot curve, amber-only per motion.ts), timed to the same
 * instant TrapCard's own label bar snaps in, so the two reinforce each other
 * rather than reading as two unrelated animations. */
const trapAlertAction = (t: number): IconAction =>
  swish(t, TRAP_ALERT_DURATION, 5, 0.7, EASE_SNAP);

const CTA_CLOSE_PULSE_DURATION = 34;
/** The close — the one beat with two pulses, and the only one that doesn't
 * fully return to rest: swish out, a short hold, a smaller second swish,
 * settling on a soft glow that persists for the rest of the video rather
 * than snapping back to off. Reads as a deliberate "that's it" rather than
 * a repeat of the other three — the restrained, geometric-mark equivalent
 * of the "theatrical bow" Sri described for a mascot ending, without the
 * bounce a literal bow would need. */
const ctaCloseAction = (t: number): IconAction => {
  const RESTING_GLOW = 0.35;
  if (t <= 14) {
    const p = t <= 7
      ? interpolate(t, [0, 7], [0, 1], { extrapolateRight: "clamp", easing: EASE_OUT })
      : interpolate(t, [7, 14], [1, 0], { extrapolateRight: "clamp", easing: EASE_OUT });
    return { leafX: 7 * p, glow: RESTING_GLOW + 0.35 * p }; // peaks at 0.7, never dips below resting
  }
  if (t <= 20) return { leafX: 0, glow: RESTING_GLOW }; // brief hold
  if (t <= CTA_CLOSE_PULSE_DURATION) {
    const p = t <= 27
      ? interpolate(t, [20, 27], [0, 1], { extrapolateRight: "clamp", easing: EASE_OUT })
      : interpolate(t, [27, CTA_CLOSE_PULSE_DURATION], [1, 0], { extrapolateRight: "clamp", easing: EASE_OUT });
    return { leafX: 4 * p, glow: RESTING_GLOW + 0.25 * p };
  }
  return { leafX: 0, glow: RESTING_GLOW }; // settled — holds to the end, deliberately
};

/**
 * Episode badge, series kicker, wordmark — present on every frame.
 *
 * A short must be unmistakably one lane or the other within a second of landing,
 * with no context and no channel page. The kicker plus the accent rule is what
 * does that work.
 *
 * The mark beside the episode number is the real FundaForge tile icon
 * (`04_Brand_Assets/Logo/FundaForge_Icon_Tile.svg`) — the rounded obsidian
 * square with the two-tone "F" (stem/top-arrow + middle-arrow) padded inside,
 * per Sri's reference image, not the bare glyph-only variant. Square viewBox
 * (0 0 100 100), so it renders at a fixed size regardless of height. Inlined
 * directly as JSX rather than fetched at runtime (unlike DiagramCard's
 * per-scene SVGs): it's small, static and never varies, so there's no reason
 * to pay a delayRender+fetch round trip for it.
 * Per Sri (18 Aug 2026): unlike the rest of the brand mark, this one DOES flip
 * by lane — Season is cyan stem/amber middle-arrow (the asset file's own
 * colours), Blueprint swaps the two, amber stem/cyan middle-arrow. Deliberate
 * exception to "the company mark doesn't change with content category" — Sri's
 * call, not assumed.
 * (18 Aug 2026: two false starts before this landed — first a flat lane-accent
 * square guessed off a compressed carousel PDF thumbnail, then the bare F
 * glyph with no tile background, then this fixed-colour version before Sri
 * clarified the swap. Lesson: check the real asset and ask rather than guess
 * on anything brand-visual.)
 *
 * Sizing/lockup locked in with Sri (19 Aug 2026) after comparing against the
 * carousel proof — the render was originally too small and undersold the
 * brand mark. Icon 110px (up from 44px originally), S1E05 46px/weight 700
 * (up from 30px/400) so it reads from the top of the F down to the mid
 * amber arrow, kicker 29px/weight 700 (up from 20px/400) left-aligned under
 * S1E05 rather than the icon. This is the spec for every future render —
 * Furniture is the single shared component for both lanes (colour swap only
 * differs by `lane`), so nothing else needs updating for Blueprint.
 */
const FundaForgeMark: React.FC<{ size?: number; lane: string; action?: IconAction }> =
({ size = 48, lane, action = REST_ACTION }) => {
  const stemColour = lane === "blueprint" ? PALETTE.amber : PALETTE.cyan;
  const midColour = lane === "blueprint" ? PALETTE.cyan : PALETTE.amber;
  return (
    <svg viewBox="0 0 100 100" width={size} height={size} style={{
      flexShrink: 0,
      // Glow is sourced from the leaf's own colour, not a generic white/accent
      // glow — reads as light coming off the piece that's moving, not a
      // separate effect layered on top of the icon.
      filter: action.glow > 0.01
        ? `drop-shadow(0 0 ${6 + action.glow * 16}px ${withAlpha(midColour, action.glow)})`
        : undefined,
    }}>
      <rect width="100" height="100" rx="20" fill={PALETTE.obsidian} />
      <g transform="translate(25.7,13) scale(0.974)">
        <rect x="0" y="0" width="15" height="76" fill={stemColour} />
        <path d="M0 0L42.5 0L50 7.5L42.5 15L0 15Z" fill={stemColour} />
        {/* The "leaf" — the one piece any beat is allowed to move, and only via
            translateX (swish IN PLACE, per Sri — never a reposition). */}
        <path d="M0 31L28.5 31L36 38.5L28.5 46L0 46Z" fill={midColour}
              style={{ transform: `translateX(${action.leafX}px)` }} />
      </g>
    </svg>
  );
};
export const Furniture: React.FC<{
  kicker: string; unitId: string; accent: string; lane: string; scenes?: Scene[];
}> = ({ kicker, unitId, accent, lane, scenes = [] }) => {
  const frame = useCurrentFrame();
  const enter = interpolate(frame, [0, 20], [0, 1], {
    extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: EASE_OUT,
  });

  // Dispatch to whichever beat's window the current frame falls in. Windows
  // don't overlap in practice — real scenes run for hundreds of frames,
  // these beats last 12-34 — so first-match-wins is safe; order here is
  // just chronological (open, diagram(s), trap, close), not a priority rule.
  const titleStart = scenes.find((s) => s.card === "TitleCard")?.start_frame ?? 0;
  const activeDiagramStart = scenes
    .filter((s) => s.card === "DiagramCard")
    .map((s) => s.start_frame)
    .find((start) => frame >= start && frame <= start + DIAGRAM_POINT_DURATION);
  const trapStart = scenes.find((s) => s.card === "TrapCard")?.start_frame;
  const ctaStart = scenes.find((s) => s.card === "CTACard")?.start_frame;

  let iconAction: IconAction = REST_ACTION;
  if (frame >= titleStart && frame <= titleStart + TITLE_ARRIVE_DURATION) {
    iconAction = titleArriveAction(frame - titleStart);
  } else if (activeDiagramStart !== undefined) {
    iconAction = diagramPointAction(frame - activeDiagramStart);
  } else if (trapStart !== undefined && frame >= trapStart && frame <= trapStart + TRAP_ALERT_DURATION) {
    iconAction = trapAlertAction(frame - trapStart);
  } else if (ctaStart !== undefined && frame >= ctaStart) {
    // Unbounded above, deliberately — ctaCloseAction holds its resting glow
    // through to the end of the video once its own pulse finishes.
    iconAction = ctaCloseAction(frame - ctaStart);
  }

  // Per Sri (19 Aug 2026, carousel reference): Blueprint's raw unit_id ("BP34")
  // is a pipeline slug, not the on-screen label — the carousel spells it out
  // as "BLUEPRINT 34". Season's "S1E05" is already the correct on-screen form,
  // so only the blueprint slug needs expanding here.
  const displayUnitId =
    lane === "blueprint" && /^BP/i.test(unitId)
      ? `BLUEPRINT ${unitId.replace(/^BP/i, "")}`
      : unitId;

  // Per Sri (19 Aug 2026): drop the "· ARC N ·" segment on-screen — it stays
  // in the video's title/description, but the video furniture itself doesn't
  // need it, and cutting it saves the width Blueprint's longer kicker needs
  // to sit on one line, same as Season's. Segment-based, not lane-gated: it
  // only fires when an "ARC N" segment is actually present.
  const displayKicker = useMemo(
    () => kicker.split(" · ").filter((seg) => !/^ARC\s*\d+$/i.test(seg.trim())).join(" · "),
    [kicker],
  );

  const kickerMaxWidth = FRAME_WIDTH - (SAFE.left + ICON_SIZE + ICON_GAP) - SAFE.right;
  const kickerFontSize = useMemo(
    () => fitKickerFontSize(displayKicker, kickerMaxWidth),
    [displayKicker, kickerMaxWidth],
  );

  return (
    <AbsoluteFill style={{ pointerEvents: "none", opacity: enter }}>
      <div style={{ position: "absolute", top: SAFE.top - 110, left: SAFE.left }}>
        <div style={{ display: "flex", alignItems: "flex-start", gap: 8 }}>
          <div style={{ marginTop: -12 }}>
            <FundaForgeMark size={110} lane={lane} action={iconAction} />
          </div>
          <div style={{ display: "flex", flexDirection: "column" }}>
            <span style={{ ...css(TYPE.badge), fontSize: 46, fontWeight: 700, color: PALETTE.white }}>
              {displayUnitId}
            </span>
            {/* Left edge lines up with the badge text, not the icon — previously this sat
                under the icon (marginLeft:17), which read as misaligned once the badge grew
                larger. Colour is `accent`, driven by the shotplan's own accent field — amber
                for Blueprint, cyan for Season — not hardcoded here, so it already tracks lane. */}
            <div style={{ ...css(TYPE.kicker), fontSize: kickerFontSize, fontWeight: 700, color: accent,
                          opacity: 0.85, letterSpacing: KICKER_LETTER_SPACING, marginTop: 6,
                          whiteSpace: "nowrap" }}>
              {displayKicker}
            </div>
          </div>
        </div>
      </div>

      <div style={{ position: "absolute", bottom: SAFE.bottom - 120, left: SAFE.left,
                    fontFamily: "Space Grotesk", fontWeight: 500, fontSize: 30,
                    color: PALETTE.white, opacity: 0.45 }}>
        FundaForge
      </div>
    </AbsoluteFill>
  );
};
