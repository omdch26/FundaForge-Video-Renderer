import React from "react";
import { AbsoluteFill } from "remotion";
import { PALETTE } from "../brand";
import { SAFE_PADDING, TYPE, css } from "../layout";
import { useEnter, riseIn, wipeIn, drawRule } from "../motion";
import { AmberText } from "./AmberText";
import type { CardProps } from "../types";

/** The workhorse: one concept, headline plus supporting line. */
export const BodyCard: React.FC<CardProps> = ({ headline, body, accent, amber_spans }) => {
  const head = useEnter(0, 14);
  const rule = useEnter(6, 18);
  const copy = useEnter(10, 16);

  return (
    <AbsoluteFill style={{ padding: SAFE_PADDING, justifyContent: "center" }}>
      <AmberText
        text={headline ?? ""}
        field="headline"
        spans={amber_spans}
        style={{ ...css(TYPE.headline), color: PALETTE.white, display: "block", ...wipeIn(head) }}
      />

      <div style={{ height: 3, width: 120, background: accent, opacity: 0.7,
                    marginTop: 32, ...drawRule(rule) }} />

      {body ? (
        <div style={{ ...riseIn(copy, 20), marginTop: 36 }}>
          <AmberText
            text={body}
            field="body"
            spans={amber_spans}
            style={{ ...css(TYPE.body), color: PALETTE.white, opacity: 0.88,
                     display: "block", maxWidth: 820 }}
          />
        </div>
      ) : null}
    </AbsoluteFill>
  );
};
