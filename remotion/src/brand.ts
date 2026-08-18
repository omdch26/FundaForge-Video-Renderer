// Brand values come from config/brand.json — the SINGLE source of truth shared
// with the Python gates. Never hardcode a colour or family name in a component.
import brand from "../../config/brand.json";

export const PALETTE = brand.palette;
export const FONTS = brand.fonts;
export const LANE_LABELS = brand.lane_labels;

export type Lane = "season" | "blueprint";

export const accentFor = (lane: Lane): string =>
  lane === "season" ? PALETTE.cyan : PALETTE.amber;

// Amber is a signal, not a decoration. These are the only legal reasons for it.
export type AmberReason =
  | "constraint" | "warning" | "trap" | "failure_mode" | "regulator_question";
