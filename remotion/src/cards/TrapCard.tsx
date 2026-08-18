import React from "react";
import { AbsoluteFill } from "remotion";
import { PALETTE } from "../brand";
import { SAFE_PADDING, TYPE, css } from "../layout";
import { useEnter, riseIn, snapIn, drawRule, EASE_SNAP } from "../motion";
import { AmberText } from "./AmberText";
import type { CardProps } from "../types";

/**
 * Slide 9 — the Interview Trap or the Regulator's Question.
 *
 * The most distinctive thing in the whole library and the most video-native
 * slide in the format: a question, the wrong answer most people give, then the
 * right one. Amber throughout, in BOTH lanes, because the question is always
 * posed by whoever can stop you — the interviewer gates your job, the regulator
 * gates your deployment.
 *
 * The answer deliberately enters late. The pause is the point: the viewer should
 * have a beat to be wrong before being corrected.
 */
export const TrapCard: React.FC<CardProps> = ({ headline, body, laneLabel, amber_spans }) => {
  const label = useEnter(0, 10, EASE_SNAP);
  const rule = useEnter(4, 16);
  const question = useEnter(8, 14);
  const answer = useEnter(34, 16); // the beat

  return (
    <AbsoluteFill style={{ padding: SAFE_PADDING, justifyContent: "center" }}>
      <div style={{ display: "flex", alignItems: "center", gap: 18, ...snapIn(label) }}>
        <div style={{ width: 6, height: 34, background: PALETTE.amber }} />
        <span style={{ ...css(TYPE.label), color: PALETTE.amber, letterSpacing: 2 }}>
          {laneLabel}
        </span>
      </div>

      <div style={{ ...riseIn(question, 22), marginTop: 40 }}>
        <AmberText
          text={headline ?? ""}
          field="headline"
          spans={amber_spans}
          style={{ ...css(TYPE.headline), color: PALETTE.white, display: "block" }}
        />
      </div>

      <div style={{ height: 3, width: "100%", maxWidth: 760, background: PALETTE.amber,
                    opacity: 0.45, marginTop: 36, ...drawRule(rule) }} />

      {body ? (
        <div style={{ ...riseIn(answer, 24), marginTop: 36 }}>
          <AmberText
            text={body}
            field="body"
            spans={amber_spans}
            style={{ ...css(TYPE.body), color: PALETTE.white, opacity: 0.9,
                     display: "block", maxWidth: 820 }}
          />
        </div>
      ) : null}
    </AbsoluteFill>
  );
};
