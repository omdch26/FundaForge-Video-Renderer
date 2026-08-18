// Mirrors schemas/shotlist.schema.json. Changing one means changing both.

export type Lane = "season" | "blueprint";

export type AmberReason =
  | "constraint" | "warning" | "trap" | "failure_mode" | "regulator_question";

export interface AmberSpan {
  field: "headline" | "body";
  start: number;
  end: number;
  reason: AmberReason;
}

export interface SceneAsset {
  kind: "svg_library" | "svg_local" | "manual_drop";
  path: string;
  slot?: string;
  animate?: "none" | "draw" | "reveal" | "scale_in";
  strip_backing_rect?: boolean;
}

export interface Scene {
  scene_id: number;
  card: "TitleCard" | "BodyCard" | "DiagramCard" | "TrapCard" | "CTACard";
  start_frame: number;
  duration_frames: number;
  slide_refs: number[];
  headline?: string;
  body?: string;
  kicker_visible?: boolean;
  asset?: SceneAsset;
  amber_spans?: AmberSpan[];
}

export interface Caption {
  text: string;
  start_frame: number;
  end_frame: number;
  emphasis?: "none" | "accent" | "constraint";
}

export interface Shotlist {
  unit_id: string;
  lane: Lane;
  series?: string;
  kicker: string;
  accent: string;
  fps: number;
  width: number;
  height: number;
  duration_frames: number;
  audio: {
    voice_file: string | null;
    voice_id?: string;
    model_id?: string;
    music_file?: string | null;
    music_gain_db?: number;
  };
  captions?: Caption[];
  scenes: Scene[];
  cta?: { tier: 1 | 2 | 3; spoken?: string; on_screen?: string; next_unit?: string | null };
}

/** Props every card receives: its own scene, plus resolved lane context. */
export type CardProps = Scene & { accent: string; lane: Lane; laneLabel: string };
