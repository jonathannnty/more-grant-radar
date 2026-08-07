#!/usr/bin/env python3
"""L4 winners feed — new SOR (93.788), RCORP (93.912), and CCBHC-Expansion
(93.696) awardees via USASpending.

These awardees just received money that can buy MORE training — the output CSV
feeds the contact pipeline for warm outreach. CCBHC (93.696) is the funded
cohort for the SM-26-014/015 post-award play: once SAMHSA's ~Nov awards post to
USASpending, this surfaces the ~94 funded clinics automatically instead of a
manual dashboard check. (93.829, the state Section-223 demonstration track, is
deliberately excluded — that's SM-26-016, not a MORE fit.)

Usage: python scripts/winners_feed.py [--months 12] [--out data/winners.csv]
"""
import argparse
import sys
if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import csv
import json
import urllib.request
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
API = "https://api.usaspending.gov/api/v2/search/spending_by_award/"

FIELDS = ["Award ID", "Recipient Name", "Award Amount", "Start Date", "End Date",
          "Awarding Agency", "Awarding Sub Agency", "recipient_id", "prime_award_recipient_id"]


def page(program, start, end, page_num):
    body = {
        "filters": {
            "award_type_codes": ["02", "03", "04", "05"],
            "program_numbers": [program],
            "time_period": [{"start_date": start, "end_date": end}],
        },
        "fields": FIELDS, "limit": 100, "page": page_num,
        "sort": "Award Amount", "order": "desc",
    }
    req = urllib.request.Request(API, data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=90) as resp:
        return json.load(resp)


def write_findings(path, source, generated, findings):
    """Also-emit the shared findings JSON contract (stdout stays unchanged)."""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(
        {"source": source, "generated": generated, "findings": findings},
        indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--months", type=int, default=12)
    ap.add_argument("--out", default="data/winners.csv")
    ap.add_argument("--json", dest="json_path", metavar="PATH",
                    help="also write findings to PATH (shared JSON contract)")
    args = ap.parse_args()

    end = date.today()
    start = end - timedelta(days=args.months * 30)
    rows = []
    findings = []
    for program, label in (("93.788", "SOR"), ("93.912", "RCORP"), ("93.696", "CCBHC")):
        p = 1
        while True:
            try:
                data = page(program, start.isoformat(), end.isoformat(), p)
            except Exception as e:  # network/API — keep partial results, never fail the run
                print(f"  ! {label} page {p} fetch failed ({type(e).__name__}: {str(e)[:80]}) "
                      "— keeping partial.", file=sys.stderr)
                break
            for r in data.get("results", []):
                agency = r.get("Awarding Sub Agency") or r.get("Awarding Agency")
                rows.append({
                    "program": label, "aln": program,
                    "recipient": r.get("Recipient Name"),
                    "award_id": r.get("Award ID"),
                    "amount": r.get("Award Amount"),
                    "start_date": r.get("Start Date"), "end_date": r.get("End Date"),
                    "agency": agency,
                })
                gid = r.get("generated_internal_id")
                rid = r.get("prime_award_recipient_id") or r.get("recipient_id")
                findings.append({
                    "kind": "winner",
                    "id": r.get("Award ID") or r.get("Recipient Name") or "",
                    "title": r.get("Recipient Name") or "",
                    "detail": (f"{label} · {agency} · {r.get('Award Amount')} "
                               f"· {r.get('Start Date')}–{r.get('End Date')} · ALN {program}"),
                    # deep-link to the award; fall back to the recipient's own record,
                    # only then to the site root — keep every finding on a primary source.
                    "url": (f"https://www.usaspending.gov/award/{gid}/" if gid
                            else f"https://www.usaspending.gov/recipient/{rid}/latest" if rid
                            else "https://www.usaspending.gov/"),
                    "fingerprint": "",
                })
            if not data.get("page_metadata", {}).get("hasNext"):
                break
            p += 1
        print(f"  {label}: {sum(1 for r in rows if r['program'] == label)} awards since {start}")

    out = ROOT / args.out
    with out.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()) if rows else
                           ["program", "aln", "recipient", "award_id", "amount", "start_date", "end_date", "agency"],
                           lineterminator="\n")
        w.writeheader()
        w.writerows(rows)
    print(f"  ✓ {out.relative_to(ROOT)} — {len(rows)} awardees for the contact pipeline")

    if args.json_path:
        write_findings(args.json_path, "winners", end.isoformat(), findings)


if __name__ == "__main__":
    main()
