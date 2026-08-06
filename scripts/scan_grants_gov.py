#!/usr/bin/env python3
"""Grants.gov Search2 sweep — the local L1 companion.

POSTs api.grants.gov/v1/api/search2 (no auth) across the radar's keyword and
ALN queries, diffs hits against grant_ids/opp numbers already in
data/grants.json, and prints a markdown report of NEW or CHANGED items only.

Usage: python scripts/scan_grants_gov.py [--rows 40]
"""
import argparse
import sys
if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import json
import urllib.request
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
API = "https://api.grants.gov/v1/api/search2"

QUERIES = [
    {"keyword": "opioid workforce training"},
    {"keyword": "medication assisted treatment"},
    {"keyword": "substance use disorder training"},
    {"keyword": "behavioral health workforce"},
    {"keyword": "chronic pain management"},
    {"keyword": "mindfulness"},
    {"keyword": "overdose prevention"},          # CDC OD2A family
    {"keyword": "criminal justice substance"},    # DOJ/BJA COSSUP family
    {"keyword": "apprenticeship behavioral health"},  # DOL/ETA
    {"keyword": "comparative effectiveness substance"},  # AHRQ (PCORI is a separate system, not Grants.gov)
    {"keyword": "behavioral health workforce education training"},  # HRSA BHWET
    {"keyword": "drug court treatment"},  # BJA / SAMHSA treatment courts
    {"keyword": "tribal opioid response"},  # SAMHSA TOR / IHS
    {"aln": "93.788"},   # State Opioid Response
    {"aln": "93.912"},   # HRSA RCORP
    {"aln": "93.243"},   # SAMHSA discretionary
    {"aln": "93.136"},   # CDC injury/overdose prevention
    {"aln": "16.838"},   # DOJ/BJA COSSUP
    {"aln": "12.420"},   # DoD CDMRP (medical research)
    {"aln": "17.285"},   # DOL registered apprenticeship
    {"aln": "93.226"},   # AHRQ research
    {"aln": "93.732"},   # HRSA BHWET
    {"aln": "16.585"},   # BJA Drug Court Discretionary
]

# HHS=93 · USDOJ=16 · DOL=17 · DoD=12 (CDMRP) · CDC rolls under HHS
RELEVANT_AGENCIES = ("HHS", "USDOJ", "DOJ", "DOL", "DOD", "DOD-")

# Broad keyword sweeps surface tangential grants; require the title to hit one of
# these MORE-relevant terms. ALN-based queries are precise program codes (SOR,
# RCORP, …) and skip this gate.
RELEVANT_TERMS = (
    "opioid", "substance use", "substance abuse", "substance misuse",
    "addiction", "overdose", "medication assisted", "medication-assisted",
    "opioid use disorder", "drug court", "behavioral health workforce",
    "mindfulness", "chronic pain", "recovery housing",
)

# The program codes we actually track (kept in sync with the ALN queries). A hit
# counts as relevant if it carries one of these — grants.gov's ALN search is fuzzy
# and otherwise returns broad NIH R01s that share an agency but not our programs.
RELEVANT_ALNS = {q["aln"] for q in QUERIES if "aln" in q}


def search(body):
    req = urllib.request.Request(
        API, data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.load(resp)["data"].get("oppHits", [])


def write_findings(path, source, generated, findings):
    """Also-emit the shared findings JSON contract (stdout stays unchanged)."""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(
        {"source": source, "generated": generated, "findings": findings},
        indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rows", type=int, default=40)
    ap.add_argument("--statuses", default="posted",
                    help='grants.gov oppStatuses filter (default "posted" = actionable; '
                         'pass "forecasted|posted" to include forecasts)')
    ap.add_argument("--json", dest="json_path", metavar="PATH",
                    help="also write findings to PATH (shared JSON contract)")
    args = ap.parse_args()

    src = json.loads((ROOT / "data" / "grants.json").read_text(encoding="utf-8"))
    known = {r["grant_id"].lower() for r in src["rows"]}
    known |= {a.lower() for r in src["rows"] for a in r.get("aliases", [])}

    seen, fresh = set(), []
    for q in QUERIES:
        body = {"oppStatuses": args.statuses, "rows": args.rows, **q}
        try:
            hits = search(body)
        except Exception as e:  # network hiccups shouldn't kill the sweep
            print(f"  ! query {q} failed: {e}")
            continue
        for h in hits:
            num = (h.get("number") or "").lower()
            if not num or num in known or h["id"] in seen:
                continue
            if not any(h.get("agencyCode", "").startswith(a) for a in RELEVANT_AGENCIES):
                continue
            # Keep only hits that carry one of our tracked program codes, or whose
            # title matches a MORE-relevant term. This drops fuzzy ALN-search results
            # (broad NIH R01s) that share an agency but neither our programs nor scope.
            cfdas = {c.strip() for c in h.get("cfdaList", [])}
            title = (h.get("title") or "").lower()
            if not (cfdas & RELEVANT_ALNS or any(t in title for t in RELEVANT_TERMS)):
                continue
            seen.add(h["id"])
            fresh.append((q, h))

    print(f"\n## Grants.gov sweep — {len(fresh)} unknown opportunities\n")
    for q, h in sorted(fresh, key=lambda x: x[1].get("closeDate") or "9999"):
        print(f"- **{h['number']}** — {h['title']}")
        print(f"  {h['agency']} · open {h.get('openDate') or '?'} · close {h.get('closeDate') or 'rolling'} "
              f"· {h['oppStatus']} · ALN {','.join(h.get('cfdaList', []))}")
        print(f"  https://www.grants.gov/search-results-detail/{h['id']}")
    if not fresh:
        print("Nothing new — all hits already tracked or out of scope.")

    if args.json_path:
        findings = [{
            "kind": "new",
            "id": h["number"],
            "title": h["title"],
            "detail": (f"{h['agency']} · open {h.get('openDate') or '?'} "
                       f"· close {h.get('closeDate') or 'rolling'} · {h['oppStatus']} "
                       f"· ALN {','.join(h.get('cfdaList', []))}"),
            "url": f"https://www.grants.gov/search-results-detail/{h['id']}",
            "fingerprint": "",
        } for q, h in sorted(fresh, key=lambda x: x[1].get("closeDate") or "9999")]
        write_findings(args.json_path, "grants_gov", date.today().isoformat(), findings)


if __name__ == "__main__":
    main()
