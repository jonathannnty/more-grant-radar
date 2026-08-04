"""Application accelerators + eligibility screen (radar v2, items 3c / 4a / 4b).

Pure functions over a grant row + a More Therapy profile. Imported by generate.py
so every row on the site carries: an eligibility label, a registration lead-time
alert, a first-draft "why MORE fits" paragraph, and an application checklist.
Stats come only from the canonical MORE evidence below — never invented.
"""
from datetime import date

# Canonical MORE evidence — single source of truth (mirrors the Grant Partner Guide).
MORE_EVIDENCE = {
    "rcts": "16 randomized controlled trials",
    "participants": "2,500+ participants",
    "funding": "$90M in NIH and DoD research funding",
    "dropout": "59% reduction in treatment dropout (Garland et al., 2022, JAMA Internal Medicine)",
    "misuse": "45% reduction in opioid misuse (three times standard group therapy)",
    "relapse": "42% reduction in drug relapse",
    "craving": "50% reduction in craving",
    "pain": "25–30% reduction in chronic pain, sustained nine months post-treatment",
}

# Known conditional eligibility gates, matched against a row's eligibility/notes text.
_GATES = [
    ("2+ consecutive years", "2+ yr state (Ohio SoS) registration", "ohio_registration_2yr"),
    ("2-year", "2+ yr state registration", "ohio_registration_2yr"),
    ("in operation for at least two years", "2+ yr in operation", "ohio_registration_2yr"),
    ("certified (or certifiable", "ADMH/state provider certification", "provider_cert"),
    ("certified by", "state provider certification", "provider_cert"),
    ("info session", "mandatory info-session attendance", "info_session"),
    ("info-session", "mandatory info-session attendance", "info_session"),
    ("engage in business in texas", "must show Texas business presence", "tx_presence"),
    ("business in texas", "must show Texas business presence", "tx_presence"),
]


def _text(r):
    return " ".join(str(r.get(k) or "") for k in ("eligibility", "notes", "accounts_needed")).lower()


def eligibility_label(r, profile):
    """Return (label, note). Honest: flags conditions, never fake-resolves an unknown."""
    fp = r.get("forprofit_direct")
    path = r.get("path") or ""
    txt = _text(r)
    conds = []
    for needle, human, key in _GATES:
        if needle in txt and human not in conds:
            # if the profile has a definite answer, fold it in; else flag to verify
            state = profile.get("gates", {}).get(key)
            conds.append(human + ("" if state is None else f" [{'met' if state else 'NOT met'}]"))
    cond = "; ".join(conds)

    if fp == "N":
        return ("Sub / line-item only", "for-profits cannot apply directly" + (f" · {cond}" if cond else ""))
    if fp == "unclear":
        return ("Verify eligibility", cond or "for-profit eligibility not yet confirmed on the primary source")
    # forprofit_direct == 'Y'
    if path.startswith("Direct"):
        return (("Direct-eligible — with conditions" if cond else "Direct-eligible"), cond)
    return ("Eligible (partner path)", cond)


def reg_alert(r, today):
    """True + message when this row needs slow federal registrations before its deadline."""
    acc = (r.get("accounts_needed") or "").lower()
    needs_reg = any(k in acc for k in ("sam", "uei", "era commons", "sba", "grants.gov"))
    if not needs_reg:
        return None
    d = r.get("deadline")
    if not d:
        return None
    days = (date.fromisoformat(d) - today).days
    if 0 <= days <= 70:
        which = []
        if "sam" in acc or "uei" in acc:
            which.append("SAM.gov/UEI")
        if "era commons" in acc:
            which.append("eRA Commons")
        if "sba" in acc:
            which.append("SBA registry")
        return f"Start {', '.join(which) or 'registrations'} now — they take weeks and this closes in {days} days."
    return None


def fit_draft(r):
    """A tailored first-draft evidence/EBP paragraph the writer edits, not starts blank."""
    funder = r.get("funder") or "the funder"
    sm = (r.get("scoring_map") or "").strip()
    where = ""
    if sm:
        clip = sm if len(sm) <= 220 else sm[:220].rstrip() + "…"
        where = f" In this opportunity MORE maps directly onto the review criteria — {clip}"
    e = MORE_EVIDENCE
    return (
        f"More Therapy proposes to train {funder}'s front-line behavioral-health and "
        f"substance-use clinicians in MORE (Mindfulness-Oriented Recovery Enhancement), an "
        f"evidence-based intervention for co-occurring opioid use disorder and chronic pain. "
        f"MORE's outcomes are documented across {e['rcts']} with {e['participants']} and {e['funding']}: "
        f"a {e['dropout']}, a {e['misuse']}, and a {e['relapse']}."
        f"{where} As a neutral third-party training partner, MORE strengthens this application's "
        f"evidence-based-practice adoption and workforce-development case without competing for the award."
    )


def checklist(r, today):
    """Ordered application pre-flight items from the fine-print we already store."""
    items = []
    if r.get("portal"):
        items.append(("Portal", r["portal"]))
    if r.get("accounts_needed"):
        items.append(("Accounts / registrations", r["accounts_needed"]))
    ra = reg_alert(r, today)
    if ra:
        items.append(("⚠ Lead time", ra))
    if r.get("match_required"):
        items.append(("Match", r["match_required"]))
    if r.get("page_limit"):
        items.append(("Page limits", r["page_limit"]))
    if r.get("attachments"):
        items.append(("Required attachments", r["attachments"]))
    return items
