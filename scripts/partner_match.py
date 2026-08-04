#!/usr/bin/env python3
"""Partner Finder (radar v2, item 1a) — match every Sub / Line-item opportunity in
data/grants.json to candidate PARTNER orgs from the MORE Contact Workflow's enriched
export, so writers/outreach get a ranked, contactable shortlist per opportunity.

The shortlists carry contact PII (names, emails), so output goes to data/partners/
which is GIT-IGNORED and never touches the public site/CSV. Hand the files to Rhea,
or paste into a Partners tab of the (private) Google Sheet.

Contact source: the newest MORE_full_list_enriched_*.csv in the contact-workflow
handoff dir. Override the dir with the MORE_CONTACTS_DIR env var.

Usage:
  python scripts/partner_match.py                 # all sub/line-item rows
  python scripts/partner_match.py --grant sm-26-014 --top 40
"""
import argparse
import csv
import json
import os
import re
import sys
from pathlib import Path

if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONTACTS_DIR = Path(
    os.environ.get("MORE_CONTACTS_DIR",
                   r"C:\Users\jonat\OneDrive\Desktop\Projects\MORE-contact-workflow\data\output\handoff"))

# Grant category → acceptable partner archetypes (tightest first).
ARCH = {
    "ccbhc": ["CCBHC / community mental health center", "Community & county behavioral health agency"],
    "mat":   ["Opioid treatment program (OTP/MOUD clinic)", "Nonprofit SUD treatment & recovery agency",
              "Community & county behavioral health agency", "FQHC / hospital / academic SUD line"],
    "sud":   ["Nonprofit SUD treatment & recovery agency", "Community & county behavioral health agency",
              "Opioid treatment program (OTP/MOUD clinic)", "FQHC / hospital / academic SUD line"],
    "genbh": ["CCBHC / community mental health center", "Community & county behavioral health agency"],
    "pain":  ["Nonprofit SUD treatment & recovery agency", "FQHC / hospital / academic SUD line",
              "Community & county behavioral health agency"],
}
ROLE_RANK = {"Finance / grants": 4, "Budget holder (exec)": 3,
             "Clinical decision-maker": 2, "Operations / program mgmt": 1}
SKIP_ROLES = {"Unusable (scraped fragment)", "Back office (forward-only)", "Front-line clinician"}
STOP = {"county", "city", "of", "the", "board", "commissioners", "department", "dhs",
        "task", "force", "council", "opioid", "abatement", "fund", "office", "planning",
        "commission", "administered", "by", "and", "+"}


def latest_contacts(directory):
    files = sorted(directory.glob("MORE_full_list_enriched_*.csv"))
    if not files:
        sys.exit(f"No MORE_full_list_enriched_*.csv in {directory} (set MORE_CONTACTS_DIR).")
    return files[-1]


def category_key(g):
    prog = (g.get("program") or "").lower()
    name = (g.get("name") or "").lower()
    cat = (g.get("category") or "").lower()
    if "ccbhc" in prog or "ccbhc" in name:
        return "ccbhc"
    if cat == "mat-moud":
        return "mat"
    if cat == "pain":
        return "pain"
    if cat == "general-bh":
        return "genbh"
    return "sud"


def geo_focus(g):
    """Place tokens (cities/counties) to concentrate on, for county-level settlement RFPs."""
    if g.get("channel") != "Settlement-county":
        return set()
    text = f"{g.get('funder','')} {g.get('name','')}"
    toks = set()
    for m in re.finditer(r"([A-Z][a-zA-Z]+)\s+(?:County|City)", text):
        toks.add(m.group(1).lower())
    # also grab a "City of X" / "Wichita KS" style city token
    for m in re.finditer(r"City of ([A-Z][a-zA-Z]+)", text):
        toks.add(m.group(1).lower())
    return {t for t in toks if t not in STOP}


def localities_only(g):
    elig = (g.get("eligibility") or "").lower()
    heart = (g.get("heart") or "").lower()
    return ("localities" in elig or "cities/counties apply" in elig
            or (g.get("path") == "Sub" and "locality" in heart))


def match(g, contacts):
    key = category_key(g)
    archset = set(ARCH[key])
    st = g.get("state")
    focus = geo_focus(g)
    loc_only = localities_only(g)
    excl_fp = g.get("forprofit_direct") == "N"
    prog = (g.get("program") or "").lower()
    gname = (g.get("name") or "").lower()

    scored = []
    for c in contacts:
        if c.get("data_quality_flag"):
            continue
        role = c.get("role_category", "")
        if role in SKIP_ROLES:
            continue
        own = c.get("org_ownership", "")
        if loc_only:
            if not own.startswith("Government - local"):
                continue
        else:
            if own == "For-profit" and excl_fp:
                continue
            if own not in ("Nonprofit", "Government - local/county", "Government - state", "unknown"):
                continue
        if st and st != "US" and (c.get("state") or "").upper() != st.upper():
            continue
        arch = c.get("org_archetype", "")
        if not loc_only and arch not in archset:
            continue

        # --- score + match-quality reasons ---
        s = float(c.get("more_fit_score") or 0)
        reasons = []
        if c.get("confidence_tier") == "high":
            s += 12
        s += {"1": 15, "2": 10, "3": 5}.get(str(c.get("send_priority") or "").strip(), 0)
        s += ROLE_RANK.get(role, 0) * 4
        accred = (c.get("accreditation") or "").strip()
        if accred not in ("", "none listed"):
            s += 8
            reasons.append(f"{accred}-accredited")
        if c.get("runs_matrix_model") == "Yes":
            s += 6
            reasons.append("already buys manualized curricula")
        if c.get("sud_treatment_center") == "Yes":
            reasons.append("SAMHSA-registered SUD provider")
        fap = c.get("federal_award_program") or ""
        in_program = bool(fap) and (fap.lower() in prog or (fap == "CCBHC" and "ccbhc" in gname))
        if in_program:
            s += 12
            reasons.append(f"already a {fap} grantee")
        if key == "mat" and (c.get("offers_moud") == "Yes" or c.get("is_opioid_treatment_program") == "Yes"):
            s += 10
            reasons.append("provides MOUD")
        in_locality = bool(focus) and (c.get("org_city") or "").strip().lower() in focus
        if in_locality:
            s += 25
            reasons.append("in the funding locality")

        # match quality label
        tight = arch == archset.__iter__().__next__() if not loc_only else True  # top archetype for the category
        strong = (in_program or in_locality or
                  (c.get("sud_treatment_center") == "Yes" and c.get("confidence_tier") == "high" and tight))
        label = "strong" if strong else "plausible"

        scored.append((s, label, reasons, c))

    # one best contact per org
    best = {}
    for s, label, reasons, c in sorted(scored, key=lambda x: -x[0]):
        org = c.get("company")
        if org not in best:
            best[org] = (s, label, reasons, c)
    return sorted(best.values(), key=lambda x: -x[0])


def why(reasons, c):
    base = [c.get("org_archetype", "").split(" (")[0], c.get("org_ownership", "")]
    fh = (c.get("funding_hook") or "").strip()
    line = " · ".join([b for b in base if b] + reasons)
    if fh and fh.lower() != "unknown":
        line += f'  |  their project: "{fh[:80]}"'
    return line


OUT_COLS = ["grant_id", "grant_name", "rank", "match", "fit", "org", "city", "state",
            "contact", "job_title", "role", "email", "email_confidence",
            "in_training_outreach", "why"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--grant", help="only this grant_id")
    ap.add_argument("--top", type=int, default=30, help="max partners written per opportunity")
    ap.add_argument("--contacts", help="explicit enriched CSV path")
    args = ap.parse_args()

    contacts_csv = Path(args.contacts) if args.contacts else latest_contacts(DEFAULT_CONTACTS_DIR)
    contacts = list(csv.DictReader(open(contacts_csv, encoding="utf-8-sig")))
    rows = json.loads((ROOT / "data" / "grants.json").read_text(encoding="utf-8"))["rows"]

    targets = [g for g in rows if g.get("path") in ("Line-item", "Sub", "Direct/Sub")]
    if args.grant:
        targets = [g for g in targets if g["grant_id"] == args.grant]

    out_dir = ROOT / "data" / "partners"
    out_dir.mkdir(parents=True, exist_ok=True)
    combined = out_dir / "partners_all.csv"
    fc = combined.open("w", encoding="utf-8", newline="")
    cw = csv.DictWriter(fc, fieldnames=OUT_COLS, lineterminator="\n")
    cw.writeheader()

    print(f"contacts: {contacts_csv.name} ({len(contacts)} rows, "
          f"{len({c['company'] for c in contacts})} orgs)")
    print(f"{len(targets)} sub/line-item opportunities\n" + "=" * 78)
    summary = []
    for g in targets:
        cands = match(g, contacts)
        summary.append((g["grant_id"], g.get("state"), g.get("path"), len(cands)))
        for i, (s, label, reasons, c) in enumerate(cands[:args.top], 1):
            cw.writerow({
                "grant_id": g["grant_id"], "grant_name": g["name"], "rank": i,
                "match": label, "fit": round(s), "org": c.get("company"),
                "city": c.get("org_city"), "state": c.get("state"),
                "contact": f"{c.get('firstname','')} {c.get('lastname','')}".strip(),
                "job_title": c.get("jobtitle"), "role": c.get("role_category"),
                "email": c.get("email"), "email_confidence": c.get("confidence_tier"),
                "in_training_outreach": c.get("previously_sent") or "No",
                "why": why(reasons, c),
            })
    fc.close()
    for gid, st, path, n in sorted(summary, key=lambda x: -x[3]):
        print(f"  {n:4} partners  {gid:30} {path:12} {st}")
    print(f"\n  ✓ data/partners/partners_all.csv  (top {args.top}/opportunity; git-ignored — contains PII)")


if __name__ == "__main__":
    main()
