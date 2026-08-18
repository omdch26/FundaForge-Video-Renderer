"""Proves the fidelity gate catches the failures it was built for.

The BP34 case is taken from a real draft that flattened "retention usually wins,
narrowly" into "retention wins". If this test ever goes green on a flat rule,
the paid-product boundary is unprotected.
"""
from dataclasses import dataclass

from pipeline.gates import fidelity


@dataclass
class FakeSlide:
    slide_number: int
    header_text: str
    body_text: str
    slide_type: str = ""
    layout_module: str = ""
    visual_direction: str = ""


@dataclass
class FakeUnit:
    unit_id: str
    lane: str
    hook_slide1: str
    slides: list

    @property
    def trap_slide(self):
        return self.slides[8]


def _bp34() -> FakeUnit:
    slides = [FakeSlide(i, f"h{i}", f"b{i}") for i in range(1, 11)]
    slides[0] = FakeSlide(1, "Delete me. The bank cannot.", "Both are law, and they point opposite ways.")
    slides[3] = FakeSlide(4, "Retention usually wins, narrowly.",
                          "Where a statutory duty to retain exists, it generally overrides an "
                          "erasure request for those specific records.")
    slides[8] = FakeSlide(9, "Reconcile erasure with seven-year retention.",
                          "Name which records are retained under which duty. It depends who is asking.")
    return FakeUnit("BP34", "blueprint", "Delete me. The bank cannot.", slides)


def _script(scenes):
    return {"lane": "blueprint", "scenes": scenes}


def test_flattened_trap_fails():
    unit = _bp34()
    findings = fidelity.check(unit, _script([
        {"slide_refs": [1], "voiceover": "Delete me. The bank cannot."},
        {"slide_refs": [4], "voiceover": "Retention wins."},
        {"slide_refs": [9], "voiceover": "The correct answer is that retention always wins."},
    ]))
    codes = {f.code for f in findings if f.severity == "fail"}
    assert "TRAP_FLATTENED" in codes or "ABSOLUTE_INTRODUCED" in codes
    assert not fidelity.passed(findings)


def test_hedges_preserved_passes():
    unit = _bp34()
    findings = fidelity.check(unit, _script([
        {"slide_refs": list(range(1, 9)), "voiceover":
            "Delete me. The bank cannot. Retention usually wins, narrowly, and only for "
            "those specific records."},
        {"slide_refs": [9, 10], "voiceover":
            "Name which records are retained under which duty. It depends who is asking."},
    ]))
    assert fidelity.passed(findings), [f.message for f in findings]


def test_rewritten_hook_fails():
    unit = _bp34()
    findings = fidelity.check(unit, _script([
        {"slide_refs": [1], "voiceover": "Today we talk about the right to be forgotten."},
        {"slide_refs": [9], "voiceover": "It depends who is asking."},
    ]))
    assert "HOOK_REWRITTEN" in {f.code for f in findings}


def test_instagram_mechanic_fails():
    unit = _bp34()
    findings = fidelity.check(unit, _script([
        {"slide_refs": [1], "voiceover": "Delete me. The bank cannot."},
        {"slide_refs": [9], "voiceover": "It depends who is asking. Save this and comment RETAIN."},
    ]))
    codes = {f.code for f in findings}
    assert "IG_KEYWORD" in codes or "IG_SAVE" in codes


def test_fabricated_number_warns():
    unit = _bp34()
    findings = fidelity.check(unit, _script([
        {"slide_refs": [1], "voiceover": "Delete me. The bank cannot."},
        {"slide_refs": [4], "voiceover":
            "Retention usually wins, narrowly, for those specific records. "
            "The bank must keep them for exactly eleven years."},
        {"slide_refs": [9], "voiceover":
            "Name which records are retained under which duty. It depends who is asking."},
    ]))
    codes = {f.code for f in findings}
    assert "POSSIBLE_FABRICATION" in codes
    warn_findings = [f for f in findings if f.code == "POSSIBLE_FABRICATION"]
    assert all(f.severity == "warn" for f in warn_findings)


def test_no_fabrication_on_faithful_script():
    unit = _bp34()
    findings = fidelity.check(unit, _script([
        {"slide_refs": list(range(1, 9)), "voiceover":
            "Delete me. The bank cannot. Retention usually wins, narrowly, and only for "
            "those specific records."},
        {"slide_refs": [9, 10], "voiceover":
            "Name which records are retained under which duty. It depends who is asking."},
    ]))
    assert "POSSIBLE_FABRICATION" not in {f.code for f in findings}


def test_fabrication_check_is_never_fatal():
    unit = _bp34()
    findings = fidelity.check(unit, _script([
        {"slide_refs": [1], "voiceover": "Delete me. The bank cannot."},
        {"slide_refs": [4], "voiceover":
            "Retention usually wins, narrowly, for those specific records, "
            "for a mandatory period of seven-hundred days."},
        {"slide_refs": [9], "voiceover":
            "Name which records are retained under which duty. It depends who is asking."},
    ]))
    fabrication_findings = [f for f in findings if f.code == "POSSIBLE_FABRICATION"]
    assert fabrication_findings  # the invented duration was caught
    assert all(f.severity == "warn" for f in fabrication_findings)  # never fails the build
