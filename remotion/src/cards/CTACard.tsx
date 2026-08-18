import React from "react";
import { AbsoluteFill } from "remotion";
import { PALETTE } from "../brand";
import { SAFE_PADDING, TYPE, css } from "../layout";
import { useEnter, riseIn, wipeIn, drawRule } from "../motion";
import type { CardProps } from "../types";

/**
 * The ending.
 *
 * The Instagram comment-keyword mechanic does NOT port — "Comment TOOLS" is
 * Instagram-plus-ManyChat and converts nothing here. 33 of 86 units carry one and
 * script generation strips them all.
 *
 * Tier 1 (every video): stay on YouTube — follow, next episode via playlist.
 * Tier 2 (passive, description only): the landing page. Nothing spoken.
 * Tier 3 (rare — end of a Season or Arc): the explicit ask, spoken aloud.
 *
 * The fidelity gate fails any script that reintroduces "save this", a comment
 * keyword, or the word Instagram.
 */
export const CTACard: React.FC<CardProps & { cta?: { tier: number; on_screen?: string; next_unit?: string | null } }> =
({ headline, body, accent, cta }) => {
  const head = useEnter(0, 14);
  const rule = useEnter(8, 18);
  const next = useEnter(14, 16);

  return (
    <AbsoluteFill style={{ padding: SAFE_PADDING, justifyContent: "center" }}>
      <h2 style={{ ...css(TYPE.headline), color: PALETTE.white, ...wipeIn(head) }}>
        {headline}
      </h2>

      {body ? (
        <div style={{ ...riseIn(next, 18), marginTop: 32 }}>
          <p style={{ ...css(TYPE.body), color: PALETTE.white, opacity: 0.85, maxWidth: 820 }}>
            {body}
          </p>
        </div>
      ) : null}

      <div style={{ height: 4, width: 220, background: accent, marginTop: 44, ...drawRule(rule) }} />

      <div style={{ ...riseIn(next, 20), marginTop: 40 }}>
        <div style={{ ...css(TYPE.label), color: accent, letterSpacing: 2 }}>
          {cta?.on_screen ?? "FOLLOW FOR THE NEXT ONE"}
        </div>
        {cta?.next_unit ? (
          <div style={{ ...css(TYPE.kicker), color: PALETTE.muted, marginTop: 14, letterSpacing: 2 }}>
            NEXT · {cta.next_unit}
          </div>
        ) : null}
      </div>
    </AbsoluteFill>
  );
};
