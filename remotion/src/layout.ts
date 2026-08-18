/**
 * Safe area, mirrored from config/pipeline.yaml.
 *
 * These insets clear YouTube's own Shorts chrome — the title and channel handle
 * along the bottom, and the like/comment/share rail down the right. Type placed
 * outside this box is covered by the app on a real phone, which is invisible in
 * a desktop preview and obvious the moment it ships.
 */
export const SAFE = { top: 220, bottom: 420, left: 72, right: 160 } as const;

export const SAFE_PADDING = `${SAFE.top}px ${SAFE.right}px ${SAFE.bottom}px ${SAFE.left}px`;

/** Type scale. Sized for legibility at arm's length on a phone, not a monitor. */
export const TYPE = {
  hook:     { size: 104, line: 1.02, weight: 700, family: "Space Grotesk" },
  headline: { size: 76,  line: 1.08, weight: 700, family: "Space Grotesk" },
  body:     { size: 42,  line: 1.38, weight: 400, family: "Inter" },
  label:    { size: 26,  line: 1.2,  weight: 700, family: "Fira Code" },
  badge:    { size: 30,  line: 1.2,  weight: 400, family: "Fira Code" },
  kicker:   { size: 20,  line: 1.2,  weight: 400, family: "Fira Code" },
  caption:  { size: 46,  line: 1.2,  weight: 600, family: "Inter" },
} as const;

export const css = (t: typeof TYPE[keyof typeof TYPE]) => ({
  fontFamily: t.family,
  fontSize: t.size,
  lineHeight: t.line,
  fontWeight: t.weight,
  margin: 0,
});
