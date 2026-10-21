#!/usr/bin/env python3
"""Promote scanner finds into data/leads.json — no human step.

Replaces the v3 "open a GitHub review Issue and wait for a human" hand-off,
which stalled for two months. Every finds/*.json the scanners emit is merged
here; each grants.gov hit is enriched from the official grants.gov
fetchOpportunity API (the federal primary source) so the lead carries its real
deadline, award ceiling, applicant types and synopsis. Leads render on the site
immediately in a clearly labelled "found by the radar, not yet verified" lane.
The weekly AI pass (scripts/ai_pass.py) verifies them into grants.json.

Lead schema (one object per lead, keyed by `key`):
  key, source, kind, id, title, funder, url, nofo_url, state, found_date,
  last_seen, deadline (YYYY-MM-DD|null), deadline_quote, cycle_watch,
  award_ceiling (number|null), applicant_types [..], forprofit_eligible
  (true|false|null), eligibility_text, synopsis, aln [..], fit_terms [..],
  status (new|expired|promoted|rejected), status_note

Usage: python scripts/promote_leads.py --finds finds [--today YYYY-MM-DD]
"""
import argparse
import html
import json
import re
import sys
import urllib.request
from datetime import date, datetime
from pathlib import Path

if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, str(Path(__file__).resolve().parent))
import runlog  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
LEADS = ROOT / "data" / "leads.json"
FETCH = "https://api.grants.gov/v1/api/fetchOpportunity"
KEEP_CLOSED_DAYS = 120
UNDATED_TTL_DAYS = 75  # an undated lead not re-seen for this long ages out

FIT_TERMS = ["opioid", "substance use", "substance abuse", "addiction", "overdose",
             "medication", "moud", "chronic pain", "pain", "mindfulness",
             "mind and body", "behavioral health", "workforce", "training",
             "treatment court", "drug court", "recovery", "reentry", "jail",
             "evidence-based", "implementation", "dissemination", "ccbhc", "fqhc"]

# Clearly not a MORE fit: dropped at the door, never shown.
NOT_FIT = re.compile(r"\b(hiv vaccine|tuberculosis|fiber optic|dale carnegie|forklift|"
                     r"aviation|cybersecurity|firearm|ammunition|janitorial|cancer|"
                     r"multiple sclerosis|als\b|malaria)", re.I)


# Federal hits must name MORE's world in the title. Program-code matches alone let in
# DoD autism/vision trials and CDC violence-prevention awards.
CORE = re.compile(r"(opioid|substance|addiction|overdose|pain|analges|mindful|mind and body|"
                  r"treatment court|drug court|recovery|behavioral health|sud|alcohol|moud|"
                  r"medication[- ]assisted|ccbhc|integrative|whole person)", re.I)


def norm(u):
    return (u or "").split("?")[0].split("#")[0].lower().rstrip("/")


def clean(s):
    s = html.unescape(str(s or ""))
    s = re.sub(r"<[^>]+>", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def gg_date(s):
    """'Nov 02, 2026 12:00:00 AM EST' -> '2026-11-02'."""
    if not s:
        return None
    try:
        return datetime.strptime(str(s)[:12], "%b %d, %Y").date().isoformat()
    except ValueError:
        return None


def fetch_opp(opp_id):
    req = urllib.request.Request(FETCH, data=json.dumps({"opportunityId": int(opp_id)}).encode(),
                                 headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=45) as r:
        return json.load(r).get("data") or {}


def enrich_grants_gov(lead):
    m = re.search(r"/search-results-detail/(\d+)", lead.get("url") or "")
    if not m:
        return lead
    try:
        d = fetch_opp(m.group(1))
    except Exception as e:  # keep the lead; enrichment is best-effort
        lead["status_note"] = f"enrichment failed: {type(e).__name__}"
        return lead
    syn = d.get("synopsis") or {}
    fc = d.get("forecast") or {}
    src = syn or fc
    types = [clean(a.get("description")) for a in src.get("applicantTypes", [])]
    lead["title"] = clean(d.get("opportunityTitle")) or lead["title"]
    lead["funder"] = clean(src.get("agencyName")) or lead.get("funder")
    lead["applicant_types"] = types
    fp = any("for profit" in t.lower() or "small business" in t.lower() for t in types)
    lead["forprofit_eligible"] = fp if types else None
    lead["eligibility_text"] = clean(src.get("applicantEligibilityDesc"))[:600]
    lead["synopsis"] = clean(src.get("synopsisDesc") or src.get("forecastDesc"))[:700]
    ceil = str(src.get("awardCeiling") or "")
    lead["award_ceiling"] = int(ceil) if ceil.isdigit() and int(ceil) > 0 else None
    lead["aln"] = [c.get("cfdaNumber") for c in d.get("cfdas", []) if c.get("cfdaNumber")]
    lead["funder_number"] = d.get("opportunityNumber")
    if syn:
        lead["deadline"] = gg_date(syn.get("responseDate"))
        lead["deadline_quote"] = f"grants.gov close date: {syn.get('responseDate') or 'not stated'}"
        lead["nofo_url"] = clean(syn.get("fundingDescLinkUrl")) or None
    else:
        lead["deadline"] = gg_date(fc.get("estApplicationResponseDate"))
        lead["deadline_quote"] = ("grants.gov forecast: est. posting " + str(fc.get("estSynopsisPostingDate"))
                                  + ", est. due " + str(fc.get("estApplicationResponseDate")))
        lead["cycle_watch"] = gg_date(fc.get("estSynopsisPostingDate"))
    return lead


def fit_terms(lead):
    text = " ".join([lead.get("title") or "", lead.get("synopsis") or ""]).lower()
    return [t for t in FIT_TERMS if t in text]


def load_leads():
    if not LEADS.exists():
        return {}
    try:
        return {l["key"]: l for l in json.loads(LEADS.read_text(encoding="utf-8")).get("leads", [])}
    except (json.JSONDecodeError, OSError, KeyError):
        return {}


def save_leads(leads, today):
    ordered = sorted(leads.values(), key=lambda l: (l.get("status") != "new", l.get("deadline") or "9999"))
    LEADS.write_text(json.dumps({
        "_comment": "Machine-found leads, not yet verified. Written by scripts/promote_leads.py and "
                    "scripts/scan_states.py; verified into grants.json by scripts/ai_pass.py.",
        "updated": today.isoformat(), "leads": ordered}, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    return ordered


def known_ids():
    src = json.loads((ROOT / "data" / "grants.json").read_text(encoding="utf-8"))
    ids = {r["grant_id"].lower() for r in src["rows"]}
    ids |= {a.lower() for r in src["rows"] for a in r.get("aliases", [])}
    ids |= {norm(r.get(k)) for r in src["rows"] for k in ("nofo_url", "source_url")} - {""}
    return ids


def expire(leads, today):
    n = 0
    for k in list(leads):
        l = leads[k]
        dl = l.get("deadline")
        if l.get("status") == "new" and dl and date.fromisoformat(dl) < today:
            l["status"], l["status_note"] = "expired", f"closed {dl}"
            n += 1
        last = date.fromisoformat(l.get("last_seen") or l.get("found_date"))
        if l.get("status") == "new" and not dl and (today - last).days > UNDATED_TTL_DAYS:
            l["status"], l["status_note"] = "expired", f"aged out (not re-seen since {last})"
            n += 1
        if l.get("status") != "new" and (today - last).days > KEEP_CLOSED_DAYS:
            del leads[k]
    return n


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--finds", default="finds")
    ap.add_argument("--today", default=date.today().isoformat())
    ap.add_argument("--no-enrich", action="store_true")
    args = ap.parse_args()
    today = date.fromisoformat(args.today)

    leads = load_leads()
    tracked = known_ids()
    added = refreshed = 0
    for fp in sorted(Path(args.finds).glob("*.json")):
        try:
            doc = json.loads(fp.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        source = doc.get("source")
        if source in ("nofo_watch", "winners"):
            continue  # tracked-row changes go to the AI pass; winners go to winners.csv
        for f in doc.get("findings", []):
            fid = str(f.get("id") or "").strip()
            if not fid or fid.lower() in tracked or norm(fid) in tracked or NOT_FIT.search(f.get("title") or ""):
                continue
            if source in ("grants_gov", "sam") and not CORE.search(f.get("title") or ""):
                continue
            key = f"{source}:{fid}"
            if key in leads:
                leads[key]["last_seen"] = today.isoformat()
                refreshed += 1
                continue
            lead = {
                "key": key, "source": source, "kind": f.get("kind", "new"), "id": fid,
                "title": clean(f.get("title")), "funder": f.get("funder") or "",
                "url": f.get("url") or "", "nofo_url": None, "state": f.get("state") or "US",
                "found_date": today.isoformat(), "last_seen": today.isoformat(),
                "deadline": f.get("deadline"), "deadline_quote": f.get("detail") or "",
                "cycle_watch": None, "award_ceiling": None, "applicant_types": [],
                "forprofit_eligible": None, "eligibility_text": "",
                "synopsis": clean(f.get("snippet") or ""), "aln": [],
                "status": "new", "status_note": "",
            }
            if source == "grants_gov" and not args.no_enrich:
                lead = enrich_grants_gov(lead)
            lead["fit_terms"] = fit_terms(lead)
            leads[key] = lead
            added += 1

    for l in leads.values():
        if l.get("status") != "new":
            continue
        if (l.get("id") or "").lower() in tracked or norm(l.get("url")) in tracked:
            l["status"], l["status_note"] = "promoted", "now a tracked row"
        elif l["source"] in ("grants_gov", "sam") and not CORE.search(l.get("title") or ""):
            l["status"], l["status_note"] = "rejected", "off-topic title"
    expired = expire(leads, today)
    ordered = save_leads(leads, today)
    active = sum(1 for l in ordered if l["status"] == "new")
    print(f"leads: +{added} new, {refreshed} re-seen, {expired} expired, {active} active")
    runlog.record("promote_leads", "ok", added=added, active=active, expired=expired)


if __name__ == "__main__":
    main()
