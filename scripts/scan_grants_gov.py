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


def search(body):
    req = urllib.request.Request(
        API, data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.load(resp)["data"].get("oppHits", [])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rows", type=int, default=40)
    args = ap.parse_args()

    src = json.loads((ROOT / "data" / "grants.json").read_text(encoding="utf-8"))
    known = {r["grant_id"].lower() for r in src["rows"]}
    known |= {a.lower() for r in src["rows"] for a in r.get("aliases", [])}

    seen, fresh = set(), []
    for q in QUERIES:
        body = {"oppStatuses": "forecasted|posted", "rows": args.rows, **q}
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


if __name__ == "__main__":
    main()
