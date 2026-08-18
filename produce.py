#!/usr/bin/env python
"""FundaForge Video Renderer — single entry point.

    python produce.py doctor
    python produce.py plan   --unit S1E05
    python produce.py run    --unit S1E05
    python produce.py run    --season 1
    python produce.py drift
"""
from __future__ import annotations

import argparse
import sys

from pipeline import config as cfgmod


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


def cmd_plan(args) -> int:
    print(f"  TODO Phase 2: dry-run cost + duration estimate for {args.unit}")
    return 0


def cmd_run(args) -> int:
    print(f"  TODO Phase 4: full pipeline for {args.unit or ('season ' + str(args.season))}")
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
