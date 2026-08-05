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
import urllib.parse
import urllib.request
from datetime import date, timedelta
from pathlib import Path

API = "https://api.sam.gov/opportunities/v2/search"
NAICS = ["611430", "621420", "611710", "624190"]
PSC = {"U008", "U009", "U099", "G004"}


def write_findings(path, source, generated, findings):
    """Also-emit the shared findings JSON contract (stdout stays unchanged)."""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(
        {"source": source, "generated": generated, "findings": findings},
        indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=7)
    ap.add_argument("--json", dest="json_path", metavar="PATH",
                    help="also write findings to PATH (shared JSON contract)")
    args = ap.parse_args()

    today = date.today().isoformat()
    key = os.environ.get("SAM_API_KEY")
    if not key:
        if args.json_path:  # workflow mode: warn + empty findings, never crash
            print("! SAM_API_KEY not set — emitting empty findings.", file=sys.stderr)
            write_findings(args.json_path, "sam", today, [])
            return
        sys.exit("Set SAM_API_KEY (free key: SAM.gov -> Account Details).")

    frm = (date.today() - timedelta(days=args.days)).strftime("%m/%d/%Y")
    to = date.today().strftime("%m/%d/%Y")
    found = 0
    findings = []
    for ncode in NAICS:
        params = urllib.parse.urlencode({
            "api_key": key, "postedFrom": frm, "postedTo": to,
            "ptype": "o", "ncode": ncode, "limit": 50,
        })
        try:
            with urllib.request.urlopen(f"{API}?{params}", timeout=60) as resp:
                data = json.load(resp)
        except Exception as e:  # rate limit / network — keep partial results, never fail the run
            print(f"  ! NAICS {ncode} fetch failed ({type(e).__name__}: {str(e)[:80]}) — skipping.",
                  file=sys.stderr)
            continue
        for opp in data.get("opportunitiesData", []):
            psc = opp.get("classificationCode") or ""
            print(f"- **{opp.get('solicitationNumber')}** — {opp.get('title')}")
            print(f"  {opp.get('fullParentPathName')} · posted {opp.get('postedDate')} · "
                  f"due {opp.get('responseDeadLine') or '?'} · NAICS {ncode} · PSC {psc}"
                  + (" ★" if psc in PSC else ""))
            print(f"  {opp.get('uiLink')}")
            found += 1
            findings.append({
                "kind": "new",
                "id": opp.get("noticeId") or opp.get("solicitationNumber") or "",
                "title": opp.get("title") or "",
                "detail": (f"{opp.get('fullParentPathName')} · posted {opp.get('postedDate')} · "
                           f"due {opp.get('responseDeadLine') or '?'} · NAICS {ncode} · PSC {psc}"
                           + (" ★" if psc in PSC else "")),
                "url": opp.get("uiLink") or "",
                "fingerprint": "",
            })
    print(f"\n{found} opportunities posted {frm}–{to}." if found else f"\nNothing new {frm}–{to}.")

    if args.json_path:
        write_findings(args.json_path, "sam", today, findings)


if __name__ == "__main__":
    main()
