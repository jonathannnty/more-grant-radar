#!/usr/bin/env python3
"""Deadline-triggered outreach wave (radar v2, item 1b + 1c).

Turns a Sub / Line-item opportunity's partner shortlist (from partner_match.py)
into a ready-to-review outreach wave: a grant-specific, per-contact draft email
(subject + body, personalized from the org's own grant + the deadline) plus a
partner_status column for the outcomes loop (1c).

DRAFTS ONLY — never sends. The output (data/waves/, git-ignored: contact PII) is
handed to the MORE Contact Workflow's compliant draft/sender, or to Rhea. The
CAN-SPAM postal footer + suppression are applied by that engine at send time.

Usage:
  python scripts/outreach_wave.py --grant sm-26-014           # one opportunity
  python scripts/outreach_wave.py --due-within 30             # all sub/line-item rows closing soon
"""
import argparse
import csv
import json
import sys
from datetime import date
from pathlib import Path

if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parents[1]
PARTNERS = ROOT / "data" / "partners" / "partners_all.csv"

BODY = """Hi {first},

I'm reaching out from More Therapy about {grant} ({due_clause}). {org_line}

MORE (Mindfulness-Oriented Recovery Enhancement) is an evidence-based clinician-training program for opioid use disorder and co-occurring chronic pain — 16 RCTs, 2,500+ participants, $90M in NIH/DoD research, a 59% reduction in treatment dropout and a 45% reduction in opioid misuse (3x standard group therapy). We are a neutral third-party training partner: we upskill your existing counselors and we do not compete for your award.

For this application, MORE gives you concrete evidence-based-practice and workforce-development language to cite{fit_clause}. If you're preparing a submission, we can provide a ready-to-drop line item, a letter of support, and the evidence summary — happy to send the one-page Grant Partner Guide.

Would a short call this week make sense to see whether it fits your application and timeline?

Best,
[SENDER NAME], More Therapy
[SENDER EMAIL] · [SENDER PHONE]
"""


def load_grants():
    return {r["grant_id"]: r for r in json.loads((ROOT / "data" / "grants.json").read_text(encoding="utf-8"))["rows"]}


def due_clause(g):
    if g.get("deadline"):
        return f"due {g['deadline']}"
    if g.get("cycle_watch"):
        return f"expected to open ~{g['cycle_watch']}"
    return "an upcoming cycle"


def subject(g):
    return f"MORE — an evidence-based-practice line for your {g['name'].split(' (')[0]} application"


def build(g, partners):
    fit = (g.get("scoring_map") or "").strip()
    fit_clause = f" — it maps to {fit[:120]}" if fit else ""
    out = []
    for p in partners:
        first = (p.get("contact") or "").split(" ")[0] or "there"
        proj = ""
        w = p.get("why") or ""
        if 'their project: "' in w:
            proj = w.split('their project: "', 1)[1].rstrip('"')
        org_line = (f'I see {p["org"]} is behind "{proj[:70]}" — this would strengthen that work.'
                    if proj else f"{p['org']} looks like a strong fit for this funding.")
        body = BODY.format(first=first, grant=g["name"].split(" (")[0], due_clause=due_clause(g),
                           org_line=org_line, fit_clause=fit_clause)
        out.append({
            "grant_id": g["grant_id"], "org": p["org"], "contact": p["contact"],
            "email": p["email"], "email_confidence": p.get("email_confidence"),
            "match": p.get("match"), "in_training_outreach": p.get("in_training_outreach"),
            "subject": subject(g), "body": body,
            "partner_status": "",  # item 1c: interested / secured / declined
        })
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--grant", help="grant_id")
    ap.add_argument("--due-within", type=int, help="all sub/line-item rows with runway <= N days")
    ap.add_argument("--top", type=int, default=25, help="max contacts per opportunity")
    args = ap.parse_args()

    if not PARTNERS.exists():
        sys.exit("Run scripts/partner_match.py first (data/partners/partners_all.csv missing).")
    rows = list(csv.DictReader(open(PARTNERS, encoding="utf-8")))
    by_grant = {}
    for r in rows:
        by_grant.setdefault(r["grant_id"], []).append(r)
    grants = load_grants()
    today = date.today()

    if args.grant:
        gids = [args.grant]
    elif args.due_within is not None:
        gids = [gid for gid, g in grants.items()
                if g.get("deadline") and 0 <= (date.fromisoformat(g["deadline"]) - today).days <= args.due_within
                and gid in by_grant]
    else:
        sys.exit("Pass --grant <id> or --due-within <days>.")

    out_dir = ROOT / "data" / "waves"
    out_dir.mkdir(parents=True, exist_ok=True)
    for gid in gids:
        g = grants.get(gid)
        if not g or gid not in by_grant:
            print(f"  ! {gid}: no partner shortlist — run partner_match.py")
            continue
        wave = build(g, by_grant[gid][:args.top])
        out = out_dir / f"{gid}_wave.csv"
        with out.open("w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(wave[0].keys()), lineterminator="\n")
            w.writeheader()
            w.writerows(wave)
        print(f"  ✓ {out.relative_to(ROOT)} — {len(wave)} draft emails · DRAFTS ONLY, review before send")
    print("\n  Hand data/waves/*.csv to the MORE Contact Workflow sender (CAN-SPAM footer + suppression) or to Rhea.")


if __name__ == "__main__":
    main()
