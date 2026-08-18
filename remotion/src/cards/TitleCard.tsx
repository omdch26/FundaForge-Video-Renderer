import React from "react";
import { AbsoluteFill } from "remotion";
import { PALETTE } from "../brand";
import { SAFE_PADDING, TYPE, css } from "../layout";
import { useEnter, wipeIn, drawRule, EASE_OUT } from "../motion";
import { AmberText } from "./AmberText";
import type { CardProps } from "../types";

/**
 * The hook. First two seconds decide everything.
 *
 * The headline text is the slide-1 hook VERBATIM — 4 to 6 words, written for a
 * cold scroll at thumbnail size, and validated across five carousel builds. The
 * fidelity gate rejects any script that rewrites it. This card's job is to get
 * it on screen fast and let it sit.
 */
export const TitleCard: React.FC<CardProps> = ({ headline, body, accent, amber_spans }) => {
  const head = useEnter(0, 16, EASE_OUT);
  const rule = useEnter(10, 20);
  const sub = useEnter(18, 14);

  return (
    <AbsoluteFill style={{ padding: SAFE_PADDING, justifyContent: "center" }}>
      <AmberText
        text={headline ?? ""}
        field="headline"
        spans={amber_spans}
        style={{ ...css(TYPE.hook), color: PALETTE.white, display: "block", ...wipeIn(head) }}
      />

      <div
        style={{
          height: 5,
          width: 180,
          background: accent,
          marginTop: 44,
          ...drawRule(rule),
        }}
      />

      {body ? (
        <AmberText
          text={body}
          field="body"
          spans={amber_spans}
          style={{
            ...css(TYPE.body),
            color: PALETTE.white,
            opacity: 0.82 * sub,
            display: "block",
            marginTop: 40,
            maxWidth: 820,
          }}
        />
      ) : null}
    </AbsoluteFill>
  );
};
