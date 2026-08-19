"""Tests for pipeline/metadata.py — the YouTube title/description/pinned-
comment drafting added 19 Aug 2026 (Furniture.tsx sizing work's follow-up).

Hermetic, same convention as test_cmd_run.py's FakeConfig: no real
SYSTEM_ROOT or config/lanes.yaml needed.
"""
import json
from pathlib import Path

from pipeline import metadata


class FakeConfig:
    def __init__(self, lanes: dict):
        self._lanes = lanes

    def lane(self, name):
        return self._lanes[name]


SEASON_TAGS = ["#MachineLearning", "#AIInterview", "#DataScience",
               "#EngineeringStudents", "#PlacementPrep", "#FundaForge",
               "#SystemsThinking", "#TechInterviews"]

BLUEPRINT_TAGS = ["#BankingAI", "#AIGovernance", "#ModelRisk",
                   "#RegulatoryCompliance", "#MachineLearning", "#FinTech",
                   "#DataScience", "#FundaForge", "#PlacementPrep",
                   "#AIInterview", "#TechInterviews"]

CFG = FakeConfig({
    "season": {"youtube_tags": SEASON_TAGS},
    "blueprint": {"youtube_tags": BLUEPRINT_TAGS},
})


def _season_shotplan(**overrides):
    sp = {
        "unit_id": "S1E05",
        "lane": "season",
        "series": "Season 1",
        "kicker": "MACHINE LEARNING · INTERVIEW FOUNDATIONS",
        "scenes": [
            {"card": "TitleCard", "headline": "99% on training. 62% on test.",
             "body": "Diagnose that gap and you've answered interview prep's "
                      "most-tested concept."},
            {"card": "TrapCard", "headline": "Your validation score keeps improving. Safe?",
             "body": "Not if you tuned against it fifty times."},
        ],
        "cta": {"tier": 1,
                "spoken": "Subscribe and turn on notifications so the next one doesn't slip by.",
                "next_unit": "S1E06"},
    }
    sp.update(overrides)
    return sp


def _blueprint_shotplan(**overrides):
    sp = {
        "unit_id": "BP34",
        "lane": "blueprint",
        "series": "Arc 3",
        "kicker": "BANKING-GRADE AI · ARC 3 · LINEAGE AND SOVEREIGNTY",
        "scenes": [
            {"card": "TitleCard", "headline": "Delete me. The bank cannot.",
             "body": "A customer exercises erasure."},
            {"card": "TrapCard", "headline": "Reconcile erasure with seven-year retention."},
        ],
        "cta": {"tier": 2, "next_unit": None},
    }
    sp.update(overrides)
    return sp


# ---------------------------------------------------------------------------
# title
# ---------------------------------------------------------------------------

def test_title_uses_hook_verbatim_and_stays_under_youtube_cap():
    title = metadata.draft_title(_season_shotplan())
    assert title.startswith("99% on training. 62% on test.")
    assert len(title) <= metadata.TITLE_HARD_CAP


def test_title_appends_kicker_topic_with_acronym_preserved():
    title = metadata.draft_title(_blueprint_shotplan())
    assert title.endswith("Banking-Grade AI")  # not "Banking-Grade Ai"


def test_title_never_exceeds_hard_cap_for_a_long_hook():
    sp = _season_shotplan()
    sp["scenes"][0]["headline"] = "A" * 150
    title = metadata.draft_title(sp)
    assert len(title) <= metadata.TITLE_HARD_CAP


# ---------------------------------------------------------------------------
# description
# ---------------------------------------------------------------------------

def test_description_leads_with_the_hook():
    desc = metadata.draft_description(_season_shotplan(), CFG)
    assert desc.startswith("99% on training. 62% on test.")


def test_description_includes_lane_tags_plus_shorts():
    desc = metadata.draft_description(_season_shotplan(), CFG)
    for tag in SEASON_TAGS:
        assert tag in desc
    assert "#Shorts" in desc


def test_description_includes_next_unit_when_present():
    desc = metadata.draft_description(_season_shotplan(), CFG)
    assert "S1E06" in desc


def test_description_omits_next_unit_line_when_absent():
    desc = metadata.draft_description(_blueprint_shotplan(), CFG)
    assert "Next up" not in desc


def test_description_keeps_arc_but_does_not_repeat_it():
    """Furniture.tsx strips '· ARC N ·' from the on-screen kicker (space
    saving); the description is exactly where Sri asked for it to still
    live. It should appear once — from `series` — not duplicated by also
    surviving inside the kicker segment."""
    desc = metadata.draft_description(_blueprint_shotplan(), CFG)
    assert desc.count("Arc 3") == 1


def test_description_falls_back_to_default_cta_when_spoken_missing():
    desc = metadata.draft_description(_blueprint_shotplan(), CFG)
    assert "subscribe" in desc.lower()
    assert "follow" not in desc.lower()  # CLAUDE.md: "Subscribe", never "Follow"


# ---------------------------------------------------------------------------
# pinned comment
# ---------------------------------------------------------------------------

def test_pinned_comment_uses_trap_card_as_discussion_hook():
    comment = metadata.draft_pinned_comment(_season_shotplan())
    assert "Your validation score keeps improving. Safe?" in comment


def test_pinned_comment_has_no_instagram_style_keyword_bait():
    comment = metadata.draft_pinned_comment(_blueprint_shotplan())
    assert "comment '" not in comment.lower()
    assert "comment \"" not in comment.lower()


def test_pinned_comment_falls_back_to_title_hook_without_trap_card():
    sp = _season_shotplan(scenes=[_season_shotplan()["scenes"][0]])  # no TrapCard
    comment = metadata.draft_pinned_comment(sp)
    assert "99% on training. 62% on test." in comment


# ---------------------------------------------------------------------------
# write_metadata
# ---------------------------------------------------------------------------

def test_write_metadata_writes_three_files_on_first_call(tmp_path):
    results = metadata.write_metadata(_season_shotplan(), CFG, tmp_path)
    assert set(results) == {"title", "description", "pinned_comment"}
    for r in results.values():
        assert r.written is True
        assert r.path.exists()
        assert r.path.parent == tmp_path
        assert r.path.read_text(encoding="utf-8").strip()


def test_write_metadata_never_overwrites_an_existing_file(tmp_path):
    """Per Sri (19 Aug 2026): a re-render must not clobber a .txt Sri may
    have already opened and hand-edited, even though the shot plan's
    headline changed since the first draft."""
    sp = _season_shotplan()
    first = metadata.write_metadata(sp, CFG, tmp_path)
    edited_title = "Sri's own hand-edited title, nothing like the hook"
    first["title"].path.write_text(edited_title + "\n", encoding="utf-8")

    sp["scenes"][0]["headline"] = "A completely different hook."
    second = metadata.write_metadata(sp, CFG, tmp_path)

    assert second["title"].written is False
    assert second["title"].path.read_text(encoding="utf-8").strip() == edited_title


def test_write_metadata_fills_in_only_the_missing_file(tmp_path):
    """description.txt and pinned_comment.txt already exist (e.g. Sri deleted
    title.txt to force a refresh of just that one) — only title.txt should
    be (re)written; the other two must be left completely untouched."""
    sp = _season_shotplan()
    first = metadata.write_metadata(sp, CFG, tmp_path)
    first["title"].path.unlink()
    untouched_description = first["description"].path.read_text(encoding="utf-8")

    second = metadata.write_metadata(sp, CFG, tmp_path)

    assert second["title"].written is True
    assert second["description"].written is False
    assert second["pinned_comment"].written is False
    assert second["description"].path.read_text(encoding="utf-8") == untouched_description
