"""Proves the humanization gate catches the mechanical patterns Section XI
bans, without trying to automate the judgement-call half (does it sound
like Sri) that CLAUDE.md explicitly leaves to a human read.
"""
from pipeline.gates import humanization


def _script(scenes):
    return {"scenes": scenes}


def test_triplet_warns():
    findings = humanization.check(_script([
        {"headline": "Fast, reliable, and scalable.", "body": "It just works."},
    ]))
    codes = {f.code for f in findings}
    assert "POSSIBLE_TRIPLET" in codes


def test_banned_word_warns():
    findings = humanization.check(_script([
        {"headline": "An innovative approach.",
         "body": "We are leveraging synergies across the platform."},
    ]))
    codes = {f.code for f in findings}
    assert "BANNED_PHRASE" in codes
    messages = " ".join(f.message for f in findings if f.code == "BANNED_PHRASE")
    assert "leveraging" in messages.lower()
    assert "synergies" in messages.lower()
    assert "innovative" in messages.lower()


def test_artificial_parallelism_warns():
    findings = humanization.check(_script([
        {"headline": "It's not a bug, it's a feature.", "body": "Ship it."},
    ]))
    codes = {f.code for f in findings}
    assert "ARTIFICIAL_PARALLELISM" in codes


def test_clean_text_passes():
    findings = humanization.check(_script([
        {"headline": "Delete me. The bank cannot.",
         "body": "A customer exercises erasure. A separate obligation requires "
                  "the bank to keep transaction records for years."},
    ]))
    assert humanization.passed(findings)


def test_all_findings_are_warn_severity():
    findings = humanization.check(_script([
        {"headline": "Fast, reliable, and scalable, leveraging synergies.",
         "body": "It's not a limitation, it's a feature."},
    ]))
    assert findings  # sanity: something was caught
    assert all(f.severity == "warn" for f in findings)
