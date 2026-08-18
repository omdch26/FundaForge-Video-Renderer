import React, { useEffect } from "react";
import { AbsoluteFill, Audio, Sequence, staticFile } from "remotion";
import { PALETTE, LANE_LABELS } from "./brand";
import { registerFonts } from "./fonts";
import { Furniture } from "./cards/Furniture";
import { Captions } from "./cards/Captions";
import { TitleCard } from "./cards/TitleCard";
import { BodyCard } from "./cards/BodyCard";
import { DiagramCard } from "./cards/DiagramCard";
import { TrapCard } from "./cards/TrapCard";
import { CTACard } from "./cards/CTACard";
import type { Shotlist, Scene } from "./types";

const CARDS = { TitleCard, BodyCard, DiagramCard, TrapCard, CTACard } as const;

/**
 * One composition for all 86 units. Everything that varies per episode arrives
 * as props from shotlist.json — nothing in this tree is episode-specific, which
 * is what keeps React out of the per-episode workflow entirely.
 */
export const Short: React.FC<Shotlist> = (props) => {
  useEffect(() => { registerFonts(); }, []);

  const { scenes, accent, kicker, unit_id, lane, audio, captions, cta } = props;
  const laneLabel = LANE_LABELS[lane];

  return (
    <AbsoluteFill style={{ backgroundColor: PALETTE.obsidian }}>
      {scenes.map((scene: Scene) => {
        const Card = CARDS[scene.card] ?? BodyCard;
        return (
          <Sequence key={scene.scene_id} from={scene.start_frame}
                    durationInFrames={scene.duration_frames}>
            <Card {...scene} accent={accent} lane={lane} laneLabel={laneLabel} cta={cta} />
          </Sequence>
        );
      })}

      <Furniture kicker={kicker} unitId={unit_id} accent={accent} lane={lane} />

      {captions?.length ? <Captions captions={captions} accent={accent} /> : null}

      {audio.voice_file ? <Audio src={staticFile(audio.voice_file)} /> : null}
      {audio.music_file ? (
        <Audio
          src={staticFile(audio.music_file)}
          volume={Math.pow(10, (audio.music_gain_db ?? -20) / 20)}
        />
      ) : null}
    </AbsoluteFill>
  );
};
