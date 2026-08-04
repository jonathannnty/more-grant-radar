#!/usr/bin/env python3
"""SAM.gov contract-opportunity sweep (training-relevant NAICS/PSC).

Needs a free API key (SAM.gov -> your Account Details page) in the SAM_API_KEY
environment variable. Personal keys are rate-limited (~10 requests/day
unverified) — this script spends one request per NAICS code, so run it at most
once a day.

Usage: SAM_API_KEY=... python scripts/scan_sam.py [--days 7]
"""
import argparse
import sys
if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import json
import os
import sys
import urllib.parse
import urllib.request
from datetime import date, timedelta

API = "https://api.sam.gov/opportunities/v2/search"
NAICS = ["611430", "621420", "611710", "624190"]
PSC = {"U008", "U009", "U099", "G004"}


def main():
    key = os.environ.get("SAM_API_KEY")
    if not key:
        sys.exit("Set SAM_API_KEY (free key: SAM.gov -> Account Details).")
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=7)
    args = ap.parse_args()

    frm = (date.today() - timedelta(days=args.days)).strftime("%m/%d/%Y")
    to = date.today().strftime("%m/%d/%Y")
    found = 0
    for ncode in NAICS:
        params = urllib.parse.urlencode({
            "api_key": key, "postedFrom": frm, "postedTo": to,
            "ptype": "o", "ncode": ncode, "limit": 50,
        })
        with urllib.request.urlopen(f"{API}?{params}", timeout=60) as resp:
            data = json.load(resp)
        for opp in data.get("opportunitiesData", []):
            psc = opp.get("classificationCode") or ""
            print(f"- **{opp.get('solicitationNumber')}** — {opp.get('title')}")
            print(f"  {opp.get('fullParentPathName')} · posted {opp.get('postedDate')} · "
                  f"due {opp.get('responseDeadLine') or '?'} · NAICS {ncode} · PSC {psc}"
                  + (" ★" if psc in PSC else ""))
            print(f"  {opp.get('uiLink')}")
            found += 1
    print(f"\n{found} opportunities posted {frm}–{to}." if found else f"\nNothing new {frm}–{to}.")


if __name__ == "__main__":
    main()
