#!/usr/bin/env python3
"""Run stamps — every automated step records what it did in data/runs.json.

The site reads this file to show real "last scanned" stamps per channel and to
flag a step that stopped running. This is what keeps the radar from dying
silently again (see specs/2026-10-20-autonomous-radar-design.md).

CLI: python scripts/runlog.py <phase> <status> [--note TEXT] [--count k=v ...]
"""
import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNS = ROOT / "data" / "runs.json"
KEEP = 300


def load():
    if not RUNS.exists():
        return []
    try:
        data = json.loads(RUNS.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except (json.JSONDecodeError, OSError):
        return []


def record(phase, status="ok", note="", **counts):
    runs = load()
    runs.append({
        "phase": phase,
        "ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "status": status,
        "note": note,
        "counts": counts,
    })
    RUNS.write_text(json.dumps(runs[-KEEP:], indent=1, ensure_ascii=False) + "\n", encoding="utf-8")


def latest_by_phase(runs=None):
    out = {}
    for r in runs if runs is not None else load():
        out[r.get("phase")] = r
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("phase")
    ap.add_argument("status")
    ap.add_argument("--note", default="")
    ap.add_argument("--count", action="append", default=[], help="k=v")
    a = ap.parse_args()
    counts = {}
    for kv in a.count:
        k, _, v = kv.partition("=")
        counts[k] = int(v) if v.isdigit() else v
    record(a.phase, a.status, a.note, **counts)
    print(f"runlog: {a.phase} {a.status}")
    sys.exit(0)
