import React from "react";
import { Composition } from "remotion";
import { Short } from "./Short";
import demo from "./demo-shotlist.json";
import type { Shotlist } from "./types";

/**
 * A single composition, fully parameterised. The Python pipeline passes
 * shotlist.json via --props; the demo below is only what the studio opens with.
 */
export const RemotionRoot: React.FC = () => (
  <Composition
    id="Short"
    component={Short as never}
    durationInFrames={(demo as unknown as Shotlist).duration_frames}
    fps={30}
    width={1080}
    height={1920}
    defaultProps={demo as never}
    calculateMetadata={({ props }) => ({
      durationInFrames: (props as Shotlist).duration_frames,
      fps: (props as Shotlist).fps,
    })}
  />
);
