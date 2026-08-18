#!/usr/bin/env python
"""FundaForge Video Renderer — single entry point.

    python produce.py doctor
    python produce.py plan   --unit S1E05
    python produce.py run    --unit S1E05
    python produce.py run    --season 1
    python produce.py drift

Script generation happens in Cowork chat, not in this codebase — Claude
reads a unit's CSV directly and drafts its shot-list JSON against
schemas/shotlist.schema.json, writing it to out/shotplans/<unit>_shotplan.json.
`plan` validates that file; it never generates one. See CLAUDE.md's
"Script generation" entry under LOCKED DECISIONS for why.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import jsonschema

from pipeline import config as cfgmod
from pipeline import source
from pipeline.gates import brand, fidelity, humanization

REPO_ROOT = Path(__file__).resolve().parent


def cmd_doctor(_args) -> int:
    """Verify wiring before anything spends a credit."""
    ok = True
    try:
        cfg = cfgmod.load()
    except Exception as e:
        print(f"  FAIL  config: {e}")
        return 1

    print(f"  ok    SYSTEM_ROOT -> {cfg.system_root}")
    for key in ("unit_index", "scripts_out", "vector_library", "fonts"):
        p = cfg.ro(key)
        mark = "ok  " if p.exists() else "FAIL"
        ok &= p.exists()
        print(f"  {mark}  {key:15s} -> {p}")

    for lane in ("season", "blueprint"):
        L = cfg.lane(lane)
        for field in ("voice_id", "model_id"):
            if not L.get(field):
                print(f"  WARN  lanes.yaml {lane}.{field} is empty — required before Phase 3")

    print("\n  TODO: font presence, ElevenLabs key reachability, Remotion install, ffmpeg on PATH")
    return 0 if ok else 1


def _fidelity_script_shape(shotplan: dict) -> dict:
    """Adapt a shot plan's scenes[] into the {"scenes": [{"slide_refs",
    "voiceover"}]} shape gates.fidelity.check() expects. Pure reshaping of
    what's already in the shot plan — introduces no new content.
    """
    return {
        "lane": shotplan.get("lane"),
        "scenes": [
            {
                "slide_refs": sc.get("slide_refs", []),
                "voiceover": f"{sc.get('headline', '')} {sc.get('body', '')}".strip(),
            }
            for sc in shotplan.get("scenes", [])
        ],
    }


def _print_findings(gate_name: str, findings: list) -> None:
    if not findings:
        print(f"  {gate_name}: no findings")
        return
    for f in findings:
        marker = "FAIL" if f.severity == "fail" else "warn"
        print(f"  [{marker}] {gate_name} {f.code}: {f.message}")


def validate_shotplan(cfg, unit_id: str, shotplans_dir: Path | None = None) -> int:
    """Load, schema-validate, and gate-check an already-authored shot plan.

    Never generates a shot plan. Returns 0 if schema-valid and no gate
    reports a fail-severity finding; nonzero otherwise. Warn-severity
    findings are printed but do not affect the return code — they are
    advisory, matching the gates' own documented design (see fidelity.py
    and humanization.py module docstrings).
    """
    shotplans_dir = shotplans_dir or (REPO_ROOT / "out" / "shotplans")
    shotplan_path = shotplans_dir / f"{unit_id}_shotplan.json"

    if not shotplan_path.exists():
        print(f"  No shot plan found for {unit_id} at {shotplan_path}")
        print(f"  Author one in Cowork chat against schemas/shotlist.schema.json, "
              f"then run `plan --unit {unit_id}` again to validate it.")
        return 1

    shotplan = json.loads(shotplan_path.read_text(encoding="utf-8"))

    schema = json.loads((REPO_ROOT / "schemas" / "shotlist.schema.json").read_text(encoding="utf-8"))
    try:
        jsonschema.validate(shotplan, schema)
        print(f"  schema: valid")
    except jsonschema.ValidationError as e:
        print(f"  [FAIL] schema: {e.message} (at {list(e.path)})")
        return 1

    unit = source.load_unit(cfg, unit_id)

    if unit.ig_status.lower() != "published":
        print(f"  WARN  {unit_id} is not yet published on Instagram (ig_status={unit.ig_status!r})")

    fidelity_script = _fidelity_script_shape(shotplan)
    fidelity_findings = fidelity.check(unit, fidelity_script)
    _print_findings("fidelity", fidelity_findings)

    humanization_findings = humanization.check(shotplan)
    _print_findings("humanization", humanization_findings)

    brand_findings = brand.check(cfg, unit, shotplan)
    _print_findings("brand", brand_findings)

    any_fail = (
        not fidelity.passed(fidelity_findings)
        or not brand.passed(brand_findings)
    )
    # humanization is warn-only by construction; passed() is still called
    # for symmetry and to catch a future change to its severity policy.
    any_fail = any_fail or not humanization.passed(humanization_findings)

    lane_cfg = cfg.lane(unit.lane)
    if lane_cfg.get("human_script_review"):
        print(f"\n  *** HUMAN SCRIPT REVIEW REQUIRED ({unit.lane}) ***")
        print(f"  Gates passing is necessary, not sufficient. This shot plan is NOT "
              f"render-ready until a human has read it against the CSV and signed off.")

    print(f"\n  verdict: {'FAIL' if any_fail else 'PASS (gates clean; human sign-off still required)'}")
    return 1 if any_fail else 0


def cmd_plan(args) -> int:
    cfg = cfgmod.load()
    return validate_shotplan(cfg, args.unit)


def cmd_run(args) -> int:
    print(f"  TODO: render + brand gate + versioned draft write for "
          f"{args.unit or ('season ' + str(args.season))} — held for a follow-up pass")
    return 0


def cmd_drift(_args) -> int:
    print("  TODO Phase 6: compare stored csv_sha256 against current CSVs")
    return 0


def main() -> int:
    p = argparse.ArgumentParser(prog="produce")
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("doctor").set_defaults(fn=cmd_doctor)

    sp = sub.add_parser("plan");  sp.add_argument("--unit", required=True); sp.set_defaults(fn=cmd_plan)
    sr = sub.add_parser("run")
    sr.add_argument("--unit"); sr.add_argument("--season", type=int); sr.set_defaults(fn=cmd_run)
    sub.add_parser("drift").set_defaults(fn=cmd_drift)

    args = p.parse_args()
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
