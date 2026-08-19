"""Phase 6 — YouTube Shorts metadata drafting: title, description, pinned comment.

Per Sri (19 Aug 2026): every render should also drop draft upload metadata into
the same out/drafts/<unit_id>/ folder as the video, so Sri can review and paste
it straight into YouTube Studio when uploading manually. This module never
uploads, publishes, or posts anything itself — see SAFETY RULES in CLAUDE.md
("Never publish", "Never send"); it only writes local .txt files for a human
to read and use.

Deliberately NOT an LLM call. Script generation (the shot plan itself) is
locked to Cowork chat per CLAUDE.md's "Script generation" decision — this
module runs inside `produce.py` as plain, deterministic Python, so it can only
ever recombine text that a human already approved at the shot-plan gate
(headlines, body copy, kicker, CTA). It cannot introduce a new claim the way
a fresh LLM call over the topic could. That's a feature, not a limitation:
metadata drafted from already-gated copy needs no new fidelity check.

Raw material used, and why:
  - scene 1 (TitleCard) headline/body — the shot plan's own cold-open hook,
    already written for maximum punch. Reused verbatim, never rewritten.
  - the TrapCard scene's headline — every unit has one (lane_label in
    lanes.yaml is literally "INTERVIEW TRAP" / "THE REGULATOR'S QUESTION"),
    and it's already phrased as a provocative question or claim — ideal
    material for a pinned comment's discussion hook, with no invention needed.
  - kicker / series / cta — identity and the brand's own locked CTA copy
    ("Subscribe...", never "Follow" — see CLAUDE.md).
  - config/lanes.yaml youtube_tags — the tag set is data, not code, so Sri can
    edit it without touching this module.

Write-once, per Sri (19 Aug 2026): write_metadata() checks each of the three
files independently and only drafts/writes the ones that don't already exist
in out_dir. A later re-render of the same unit (v2, v3, ...) never overwrites
a file Sri may have already opened and hand-edited. See write_metadata()'s
own docstring for how to force a genuine refresh.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

TITLE_HARD_CAP = 100          # YouTube's own title character limit
DESCRIPTION_HOOK_CAP = 100    # roughly what's visible before "...more" on mobile
MAX_HASHTAGS = 15             # YouTube stops treating hashtags as tags past this count

ACRONYMS = {"AI", "ML", "KYC", "GDPR", "CTO", "CEO", "API", "SQL", "LLM", "AML", "CFO", "ROI"}


@dataclass
class Metadata:
    title: str
    description: str
    pinned_comment: str


@dataclass
class WriteResult:
    path: Path
    written: bool  # True if this call created the file; False if it already
                    # existed and was left untouched (see write_metadata).


# ---- small text helpers ---------------------------------------------------

def _smart_titlecase(phrase: str) -> str:
    """Title-case a phrase while preserving known acronyms (AI, KYC, ...).

    str.title()/.capitalize() alone turns "BANKING-GRADE AI" into
    "Banking-Grade Ai" — wrong for exactly the kind of term this pipeline's
    topics are full of.
    """
    def fix(word: str) -> str:
        core = re.sub(r"[^A-Za-z]", "", word)
        return word if core.upper() in ACRONYMS else word.capitalize()

    out = []
    for word in phrase.split(" "):
        if "-" in word:
            out.append("-".join(fix(p) for p in word.split("-")))
        else:
            out.append(fix(word))
    return " ".join(out)


def _scene(shotplan: dict, card: str) -> dict | None:
    for sc in shotplan.get("scenes", []):
        if sc.get("card") == card:
            return sc
    return None


def _human_unit_label(unit_id: str, lane: str) -> str:
    """Mirrors Furniture.tsx's displayUnitId — "BP34" -> "Blueprint 34" — but
    title-cased rather than all-caps, since this lands in prose, not on-screen
    furniture. Keep these two in sync if the slug format ever changes.
    """
    if lane == "blueprint" and re.match(r"^BP", unit_id, re.I):
        return f"Blueprint {re.sub(r'^BP', '', unit_id, flags=re.I)}"
    return unit_id


def _kicker_topic(kicker: str) -> str:
    """First segment of the kicker (before the first ' · '), title-cased.

    Season: "MACHINE LEARNING · INTERVIEW FOUNDATIONS" -> "Machine Learning".
    Blueprint: "BANKING-GRADE AI · LINEAGE AND SOVEREIGNTY" -> "Banking-Grade AI"
    (the "· ARC N ·" segment Furniture.tsx strips on-screen was never in the
    first position, so nothing extra to strip here).
    """
    first = kicker.split(" · ")[0].strip()
    return _smart_titlecase(first)


# ---- the three drafts ------------------------------------------------------

def draft_title(shotplan: dict) -> str:
    """Hook + ' | ' + topic keyword, hard-capped at 100 chars.

    The hook is scene 1's headline verbatim — it's already written as the
    cold open, i.e. already optimised for the first half-second of watch
    time, which is the same job a Shorts title does. The topic suffix adds
    the searchable keyword a bare hook line wouldn't carry, without
    padding out the curiosity-driving part of the title.
    """
    title_scene = _scene(shotplan, "TitleCard") or shotplan["scenes"][0]
    hook = title_scene["headline"].strip()
    topic = _kicker_topic(shotplan.get("kicker", ""))

    candidate = hook
    if topic and len(hook) + len(topic) + 3 <= 95:
        candidate = f"{hook} | {topic}"

    if len(candidate) > TITLE_HARD_CAP:
        candidate = candidate[: TITLE_HARD_CAP - 3].rstrip() + "..."
    return candidate


def draft_description(shotplan: dict, cfg) -> str:
    """Hook line -> value paragraph -> CTA -> series/next-unit -> hashtags.

    Structure follows standard Shorts description practice: the first ~100
    characters are what's visible before YouTube truncates behind "...more"
    on mobile, so the hook goes first, verbatim from the shot plan (never
    invented). Hashtags are lane data from config/lanes.yaml, not hardcoded
    here, plus #Shorts — flagged as a Phase 6 nice-to-have back when the
    Furniture sizing work was done (see CLAUDE.md, "Shorts format" entry).
    """
    title_scene = _scene(shotplan, "TitleCard") or shotplan["scenes"][0]
    hook = title_scene["headline"].strip()
    hook_payoff = title_scene.get("body", "").strip()

    lane = shotplan["lane"]
    lane_cfg = cfg.lane(lane)
    unit_label = _human_unit_label(shotplan["unit_id"], lane)
    # Drop any "ARC N" segment here too — `series` (below) already carries it,
    # and repeating it reads as a typo, not as emphasis. Same filter as
    # Furniture.tsx's displayKicker, kept in sync deliberately (see that
    # component's docstring for why it's stripped from the video furniture).
    kicker_segments = [seg.strip() for seg in shotplan["kicker"].split(" · ")
                        if not re.match(r"^ARC\s*\d+$", seg.strip(), re.I)]
    kicker_human = " · ".join(_smart_titlecase(seg) for seg in kicker_segments)

    lane_blurb = {
        "season": "Part of FundaForge's Season — interview-ready machine learning, "
                   "one tested concept at a time.",
        "blueprint": "Part of FundaForge's Blueprint series — banking-grade AI "
                      "governance, explained precisely enough to defend in a room "
                      "full of regulators.",
    }.get(lane, "Part of FundaForge.")

    cta = shotplan.get("cta") or {}
    cta_line = cta.get("spoken") or "Subscribe and turn on notifications for the next one."
    next_unit = cta.get("next_unit")

    lines = [
        f"{hook} {hook_payoff}".strip(),
        "",
        lane_blurb,
        "",
        cta_line,
        "",
        f"{shotplan.get('series', '')} · {unit_label} · {kicker_human}".strip(" ·"),
    ]
    if next_unit:
        lines.append(f"Next up: {next_unit}")

    tags = list(lane_cfg.get("youtube_tags", []))
    if "#Shorts" not in tags:
        tags.append("#Shorts")
    tags = tags[:MAX_HASHTAGS]

    lines += ["", " ".join(tags)]
    return "\n".join(lines).strip() + "\n"


def draft_pinned_comment(shotplan: dict) -> str:
    """A discussion question (from the TrapCard's own headline — already
    written as a provocation, not invented here) plus a low-key CTA restate.

    No "comment X below" keyword bait — the shot-list schema's own CTA note
    explicitly rules that pattern out as an Instagram-era mechanic that
    doesn't port (see schemas/shotlist.schema.json, cta._note).
    """
    trap = _scene(shotplan, "TrapCard")
    hook_line = trap["headline"].strip() if trap else \
        (_scene(shotplan, "TitleCard") or shotplan["scenes"][0])["headline"].strip()

    cta = shotplan.get("cta") or {}
    cta_line = cta.get("spoken") or "Subscribe and turn on notifications for the next one."

    return f"{hook_line} Curious how you'd call it — drop your answer below.\n\n{cta_line}\n"


def write_metadata(shotplan: dict, cfg, out_dir: Path) -> dict[str, WriteResult]:
    """Draft and write all three files into out_dir (same folder as the
    video draft) — but only the ones that don't already exist there.

    Per Sri (19 Aug 2026): once a file has been drafted for a unit, a later
    re-render (v2, v3, ...) must never touch it again, even though the
    underlying shot plan hasn't changed — Sri may have already opened and
    hand-edited the draft, and a silent overwrite would discard that. Each of
    the three files is checked and skipped independently, so e.g. an edited
    title survives even if description.txt still needs (re)writing for the
    first time. To force a genuine refresh, delete the specific .txt file(s)
    first — there is no "regenerate" flag, deliberately, so this can't happen
    by accident.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    unit_id = shotplan["unit_id"]

    candidate_paths = {
        "title": out_dir / f"{unit_id}_title.txt",
        "description": out_dir / f"{unit_id}_description.txt",
        "pinned_comment": out_dir / f"{unit_id}_pinned_comment.txt",
    }

    # Only draft the text that's actually needed — e.g. if title.txt exists
    # but description.txt doesn't, don't bother computing draft_title() at all.
    to_write = {label: p for label, p in candidate_paths.items() if not p.exists()}

    if to_write:
        meta = Metadata(
            title=draft_title(shotplan),
            description=draft_description(shotplan, cfg),
            pinned_comment=draft_pinned_comment(shotplan),
        )
        content = {
            "title": meta.title + "\n",
            "description": meta.description,
            "pinned_comment": meta.pinned_comment,
        }
        for label, p in to_write.items():
            p.write_text(content[label], encoding="utf-8")

    return {
        label: WriteResult(path=p, written=label in to_write)
        for label, p in candidate_paths.items()
    }
