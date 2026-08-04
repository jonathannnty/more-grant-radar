#!/usr/bin/env python3
"""Win/loss learning loop (radar v2, item 3a).

Aggregates DECIDED outcomes (Won / Lost / Passed, from the Team tab export
data/team.csv + data/archive.csv reasons) against grants.json, and reports
conversion by channel / path / for-profit-eligibility / category — the feedback
that recalibrates the 1–5 likelihood scoring to what actually wins for MORE.

Accuracy is the product; this is the loop that sharpens it. With no decided
outcomes yet it says so, and the machinery is ready for the first Won/Lost/Passed.

Usage: python scripts/learning_loop.py   → prints + writes data/learning_report.md
"""
import csv
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parents[1]
DECIDED = {"Won", "Lost", "Passed", "Submitted", "Pursuing-Direct", "Pursuing-Sub"}
WON = {"Won"}
LOST = {"Lost", "Passed"}


def load_team():
    f = ROOT / "data" / "team.csv"
    if not f.exists():
        return {}
    with f.open(encoding="utf-8-sig", newline="") as fh:
        return {r["grant_id"].strip(): r for r in csv.DictReader(fh) if r.get("grant_id")}


def load_archive():
    f = ROOT / "data" / "archive.csv"
    out = []
    if f.exists():
        with f.open(encoding="utf-8-sig", newline="") as fh:
            out = list(csv.DictReader(fh))
    return out


def pct(w, n):
    return f"{100*w/n:.0f}%" if n else "—"


def main():
    rows = {r["grant_id"]: r for r in json.loads((ROOT / "data" / "grants.json").read_text(encoding="utf-8"))["rows"]}
    team = load_team()

    # merge status onto rows; include archived decided rows too
    records = []
    for gid, r in rows.items():
        st = (team.get(gid, {}) or {}).get("status") or "New"
        records.append({**r, "status": st, "why_passed": (team.get(gid, {}) or {}).get("why_passed", "")})
    for a in load_archive():
        if a.get("reason") in ("won", "lost", "passed"):
            records.append({**a, "status": a["reason"].capitalize(),
                            "likelihood": float(a.get("likelihood") or 0)})

    decided = [r for r in records if r["status"] in DECIDED]
    won = [r for r in decided if r["status"] in WON]

    lines = ["# Radar scoring calibration — win/loss learning loop", ""]
    lines.append(f"- tracked rows: **{len(records)}** · decided (Won/Lost/Passed/Submitted/Pursuing): "
                 f"**{len(decided)}** · won: **{len(won)}**")

    if len(decided) < 3:
        lines += ["",
                  "**Not enough decided outcomes yet to calibrate.** The loop is wired and reads the "
                  "Team tab's status + why_passed. As rows are marked Won / Lost / Passed (with a reason), "
                  "this report fills in conversion by channel / path / eligibility / category and flags where "
                  "the likelihood rubric is over- or under-scoring. Start logging outcomes at each Monday sync.",
                  "",
                  "Statuses that count as decided: " + ", ".join(sorted(DECIDED)) + "."]
    else:
        def breakdown(dim):
            agg = defaultdict(lambda: [0, 0])  # key -> [won, decided]
            for r in decided:
                k = r.get(dim) or "—"
                agg[k][1] += 1
                if r["status"] in WON:
                    agg[k][0] += 1
            out = ["", f"## By {dim}", "", "| " + dim + " | decided | won | rate |", "|---|---:|---:|---:|"]
            for k, (w, n) in sorted(agg.items(), key=lambda x: -x[1][1]):
                out.append(f"| {k} | {n} | {w} | {pct(w, n)} |")
            return out
        for dim in ("channel", "path", "forprofit_direct", "category", "funder"):
            lines += breakdown(dim)
        # calibration hint: are wins concentrated at high or low likelihood?
        hi = [r for r in decided if float(r.get("likelihood") or 0) >= 4]
        lo = [r for r in decided if float(r.get("likelihood") or 0) <= 2]
        lines += ["", "## Likelihood calibration",
                  f"- high-likelihood (4–5) rows: {sum(1 for r in hi if r['status'] in WON)}/{len(hi)} won ({pct(sum(1 for r in hi if r['status'] in WON), len(hi))})",
                  f"- low-likelihood (1–2) rows: {sum(1 for r in lo if r['status'] in WON)}/{len(lo)} won ({pct(sum(1 for r in lo if r['status'] in WON), len(lo))})",
                  "- if low-likelihood rows are winning as often as high, the rubric needs re-weighting toward what those rows share."]
        why = [r.get("why_passed") for r in decided if r["status"] == "Passed" and r.get("why_passed")]
        if why:
            lines += ["", "## Why we passed (decision log)"] + [f"- {w}" for w in why]

    report = "\n".join(lines) + "\n"
    (ROOT / "data" / "learning_report.md").write_text(report, encoding="utf-8")
    print(report)
    print(f"  ✓ data/learning_report.md")


if __name__ == "__main__":
    main()
