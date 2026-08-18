import React from "react";
import { PALETTE } from "../brand";
import type { AmberSpan } from "../types";

/**
 * Renders text with amber applied only to declared spans.
 *
 * Amber is never chosen here — it is declared upstream in the shotlist with a
 * reason, and the brand gate rejects any reason outside constraint, warning,
 * trap, failure_mode and regulator_question. This component just draws what it
 * is told, so there is exactly one place where amber can be introduced and
 * exactly one gate guarding it.
 */
export const AmberText: React.FC<{
  text: string;
  field: "headline" | "body";
  spans?: AmberSpan[];
  style?: React.CSSProperties;
}> = ({ text, field, spans = [], style }) => {
  const mine = spans
    .filter((s) => s.field === field)
    .sort((a, b) => a.start - b.start);

  if (mine.length === 0) return <span style={style}>{text}</span>;

  const parts: React.ReactNode[] = [];
  let cursor = 0;

  mine.forEach((span, i) => {
    if (span.start > cursor) parts.push(<span key={`p${i}`}>{text.slice(cursor, span.start)}</span>);
    parts.push(
      <span key={`a${i}`} style={{ color: PALETTE.amber }}>
        {text.slice(span.start, span.end)}
      </span>
    );
    cursor = span.end;
  });
  if (cursor < text.length) parts.push(<span key="tail">{text.slice(cursor)}</span>);

  return <span style={style}>{parts}</span>;
};
