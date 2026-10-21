#!/usr/bin/env python3
"""State / county / abatement discovery — the channel that never ran in v3.

Two automatic feeds, both emitting the shared findings contract into finds/:

1. Settlement-tracker live list (finds/settlement_tracker.json). The public
   OpioidSettlementTracker "Community Grant Tracker" publishes open county, city
   and state settlement grant windows with a due date and the issuing entity's
   own application URL. Used for discovery only: each lead links to the
   entity's page, which is the primary source.

2. Link-delta watcher (finds/states.json). Fetches every watched page (the
   50-state + DC behavioral-health and settlement pages in grants.json's
   state_directory, every tracked state/county row's source page, and every
   entity page the tracker has ever listed) and diffs its links against
   data/state_link_baseline.json. A NEW link whose text or URL looks like a
   funding solicitation (RFP / RFA / NOFA / grant application / mini-grant /
   funding opportunity ...) becomes a lead. On a page's first visit only links
   naming 2026/2027 or FY26/FY27 are promoted, so the first run is not a flood.

Never edits grants.json. Usage:
  python scripts/scan_states.py --out finds [--today YYYY-MM-DD] [--workers 12]
"""
import argparse
import html
import json
import re
import sys
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from pathlib import Path

if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, str(Path(__file__).resolve().parent))
import runlog  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
BASELINE = ROOT / "data" / "state_link_baseline.json"
WATCH_EXTRA = ROOT / "data" / "watch_pages.json"
TRACKER_FEED = ("https://script.google.com/macros/s/AKfycbynYDZ1Db2qE7Bhia_sI-lCEWOiIQbHRMWnBtGZzetZFJLS77t"
                "nCmdgvA-AiRep_0ol/exec")
TRACKER_PAGE = "https://www.opioidsettlementtracker.com/communitygranttracker"
UA = "Mozilla/5.0 (compatible; MORE-Grant-Radar/4.0; +https://jonathannnty.github.io/more-grant-radar/)"

STATES = {
    "Alabama": "AL", "Alaska": "AK", "Arizona": "AZ", "Arkansas": "AR", "California": "CA",
    "Colorado": "CO", "Connecticut": "CT", "Delaware": "DE", "District of Columbia": "DC",
    "Florida": "FL", "Georgia": "GA", "Hawaii": "HI", "Idaho": "ID", "Illinois": "IL",
    "Indiana": "IN", "Iowa": "IA", "Kansas": "KS", "Kentucky": "KY", "Louisiana": "LA",
    "Maine": "ME", "Maryland": "MD", "Massachusetts": "MA", "Michigan": "MI", "Minnesota": "MN",
    "Mississippi": "MS", "Missouri": "MO", "Montana": "MT", "Nebraska": "NE", "Nevada": "NV",
    "New Hampshire": "NH", "New Jersey": "NJ", "New Mexico": "NM", "New York": "NY",
    "North Carolina": "NC", "North Dakota": "ND", "Ohio": "OH", "Oklahoma": "OK", "Oregon": "OR",
    "Pennsylvania": "PA", "Rhode Island": "RI", "South Carolina": "SC", "South Dakota": "SD",
    "Tennessee": "TN", "Texas": "TX", "Utah": "UT", "Vermont": "VT", "Virginia": "VA",
    "Washington": "WA", "West Virginia": "WV", "Wisconsin": "WI", "Wyoming": "WY",
}

SOLICIT = re.compile(
    r"\b(rfps?|rfas?|rfqs?|nofas?|nofos?|requests? for (proposals?|applications?|qualifications)|"
    r"funding (opportunit|announcement|application|round|cycle)|grant (opportunit|application|round|cycle|program)|"
    r"apply for (funding|a grant)|solicitation|mini-?grants?|community grants?|notice of funding|"
    r"accepting (applications|proposals)|now open|open (call|solicitation))", re.I)
RELEVANT = re.compile(r"(opioid|substance|sud\b|addiction|behavioral|mental|recovery|treatment|overdose|"
                      r"workforce|training|abatement|settlement|remediation|prevention|harm reduction)", re.I)
SKIP = re.compile(r"(\bawards?\b|\bawarded\b|awardee|award summary|recipients|minutes|agenda|press release|\breports?\b|feedback|"
                  r"q\s?&\s?a|questions and answers|response form|addend|conditions\b|"
                  r"block grant application|block grant report|mhbg|subg app|"
                  r"/news/?$|facebook\.com|twitter\.com|x\.com/|linkedin\.com|instagram\.com|youtube\.com|"
                  r"mailto:|tel:|javascript:|#$|login|sign[- ]?in|privacy|accessibility|sitemap)", re.I)
RECENT = re.compile(r"(2026|2027|fy\s?-?2?6\b|fy\s?-?2?7\b|fy\s?20?2[67])", re.I)
DUE_NEAR = re.compile(
    r"(due|deadline|submi\w+|close[sd]?|no later than|accepted (until|through))[^.]{0,80}?"
    r"(?P<d>(january|february|march|april|may|june|july|august|september|october|november|december)\s+\d{1,2},?\s+20\d\d"
    r"|\d{1,2}/\d{1,2}/20\d\d)", re.I)
MONTHS = {m: i + 1 for i, m in enumerate(["january", "february", "march", "april", "may", "june", "july",
                                          "august", "september", "october", "november", "december"])}


def fetch(url, limit=1_500_000, timeout=30):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "text/html,*/*"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        ctype = r.headers.get("Content-Type", "")
        return r.geturl(), ctype, r.read(limit).decode("utf-8", "replace")


def links_of(base, raw):
    out = {}
    for m in re.finditer(r"<a\b[^>]*?href\s*=\s*[\"']([^\"'#][^\"']*)[\"'][^>]*>(.*?)</a>", raw, re.I | re.S):
        href = html.unescape(m.group(1)).strip()
        text = re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", m.group(2)))).strip()
        try:
            absu = urllib.parse.urljoin(base, href).split("#")[0]
        except ValueError:
            continue
        if absu.startswith("http") and absu != base:
            out.setdefault(absu, text[:200])
    return out


def page_text(url):
    """Plain text of an HTML page or (if pypdf is installed) the first pages of a PDF."""
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as r:
        ctype = r.headers.get("Content-Type", "").lower()
        body = r.read(8_000_000)
    if "pdf" in ctype or url.lower().split("?")[0].endswith(".pdf") or body[:5] == b"%PDF-":
        try:
            import io
            from pypdf import PdfReader
        except ImportError:
            return ""
        reader = PdfReader(io.BytesIO(body))
        text = " ".join((pg.extract_text() or "") for pg in reader.pages[:6])
    else:
        text = re.sub(r"<script[\s\S]*?</script>|<style[\s\S]*?</style>", " ", body.decode("utf-8", "replace"), flags=re.I)
        text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", html.unescape(text))


def parse_due(text):
    """Latest date that sits right after a due/deadline/submission phrase, with its quote.
    The latest one is the application due date in practice (inquiry and webinar dates
    come earlier). Returns (iso_date|None, quote|None); never guesses."""
    best = None
    for m in DUE_NEAR.finditer(text):
        s = m.group("d")
        try:
            if "/" in s:
                mo, dd, yy = s.split("/")
                d = date(int(yy), int(mo), int(dd))
            else:
                parts = re.match(r"(\w+)\s+(\d{1,2}),?\s+(\d{4})", s)
                d = date(int(parts.group(3)), MONTHS[parts.group(1).lower()], int(parts.group(2)))
        except (ValueError, KeyError, AttributeError):
            continue
        if best is None or d > best[0]:
            best = (d, re.sub(r"\s+", " ", m.group(0)).strip()[:180])
    return (best[0].isoformat(), best[1]) if best else (None, None)


def watch_list(src, extra):
    pages = []
    for s in src.get("state_directory", []):
        code = STATES.get(s["state"], "")
        for k in ("url", "settlement_url"):
            if s.get(k):
                pages.append({"url": s[k], "state": code, "who": s.get("agency", s["state"])[:120],
                              "settlement": k == "settlement_url"})
    for r in src["rows"]:
        if r.get("state") not in (None, "", "US") and r.get("source_url"):
            pages.append({"url": r["source_url"], "state": r["state"], "who": r.get("funder", ""),
                          "settlement": "Settlement" in (r.get("channel") or "")})
    pages += extra
    seen, out = set(), []
    for p in pages:
        if p["url"] not in seen:
            seen.add(p["url"])
            out.append(p)
    return out


def tracker_feed(today, extra):
    """Open windows from the settlement tracker, plus growth of the watch list."""
    findings, note = [], ""
    try:
        _, _, raw = fetch(TRACKER_FEED, limit=5_000_000, timeout=90)
        data = json.loads(raw)
    except Exception as e:
        return findings, f"tracker feed failed: {type(e).__name__}", extra
    live = data.get("liveGrants") or {}
    upd = live.get("updateDate") or data.get("lastUpdated") or "?"
    note = f"tracker list updated {upd}"
    known = {p["url"] for p in extra}
    for r in live.get("rows", []):
        due = (r.get("due") or "").strip()
        url = (r.get("appinfo_url") or "").strip()
        if not url:
            continue
        code = STATES.get(r.get("state", ""), "")
        if url not in known:
            extra.append({"url": url, "state": code, "who": r.get("entity", ""), "settlement": True})
            known.add(url)
        if due != "rolling":
            try:
                if date.fromisoformat(due) < today:
                    continue
            except ValueError:
                continue
        entity = r.get("entity", "")
        findings.append({
            "kind": "new", "id": url, "state": code, "url": url, "funder": entity,
            "title": f"{entity} ({r.get('state', '')}): opioid settlement funding " +
                     ("— rolling applications" if due == "rolling" else f"— due {due}"),
            "deadline": None if due == "rolling" else due,
            "detail": (f"Listed on OpioidSettlementTracker's Community Grant Tracker (list updated {upd}) as "
                       + ("rolling / open until funds run out" if due == "rolling" else f"due {due}")
                       + ". Confirm on the entity's page."),
            "snippet": re.sub(r"<[^>]+>", "", r.get("note_html") or "")[:300],
        })
    return findings, note, extra


def scan_page(p):
    try:
        final, ctype, raw = fetch(p["url"])
    except Exception as e:
        return p, None, f"{type(e).__name__}"
    if "html" not in ctype.lower() and "<a " not in raw[:20000].lower():
        return p, {}, "not html"
    return p, links_of(final, raw), "ok"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="finds")
    ap.add_argument("--today", default=date.today().isoformat())
    ap.add_argument("--workers", type=int, default=12)
    ap.add_argument("--max-pages", type=int, default=0, help="debug: cap pages scanned")
    args = ap.parse_args()
    today = date.fromisoformat(args.today)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    src = json.loads((ROOT / "data" / "grants.json").read_text(encoding="utf-8"))
    extra = json.loads(WATCH_EXTRA.read_text(encoding="utf-8")) if WATCH_EXTRA.exists() else []
    base = json.loads(BASELINE.read_text(encoding="utf-8")) if BASELINE.exists() else {}

    t_find, t_note, extra = tracker_feed(today, extra)
    WATCH_EXTRA.write_text(json.dumps(extra, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    (out / "settlement_tracker.json").write_text(json.dumps(
        {"source": "settlement_tracker", "generated": today.isoformat(), "findings": t_find},
        indent=1, ensure_ascii=False) + "\n", encoding="utf-8")

    pages = watch_list(src, extra)
    if args.max_pages:
        pages = pages[: args.max_pages]
    findings, ok, failed = [], 0, []
    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        results = list(ex.map(scan_page, pages))
    for p, links, status in results:
        if links is None:
            failed.append((p["url"], status))
            continue
        ok += 1
        first_visit = p["url"] not in base
        prev = set(base.get(p["url"], []))
        for href, text in links.items():
            if href in prev:
                continue
            blob = f"{text} {urllib.parse.unquote(href)}"
            if SKIP.search(blob) or not SOLICIT.search(blob):
                continue
            if not (p["settlement"] or RELEVANT.search(blob)):
                continue
            if first_visit and not RECENT.search(blob):
                continue
            findings.append({"kind": "new", "id": href, "state": p["state"], "url": href,
                             "funder": p["who"], "title": text or href.rsplit("/", 1)[-1],
                             "detail": f"New funding link on {p['url']}", "snippet": "",
                             "deadline": None, "_page": p["url"]})
        if links:
            base[p["url"]] = sorted(links)[:800]

    # Best-effort deadline read on each new HTML lead (quoted, never guessed).
    def due_of(f):
        if f["url"].lower().split("?")[0].endswith((".docx", ".doc", ".xlsx")):
            return f
        try:
            text = page_text(f["url"])
            dl, quote = parse_due(text)
            if dl:  # past dates are kept too: promote_leads then files the lead as closed
                f["deadline"], f["detail"] = dl, f"{f['detail']} · page says: “{quote}”"
        except Exception:
            pass
        return f
    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        findings = list(ex.map(due_of, findings[:150]))
    for f in findings:
        f.pop("_page", None)

    BASELINE.write_text(json.dumps(base, indent=0, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    (out / "states.json").write_text(json.dumps(
        {"source": "states", "generated": today.isoformat(), "findings": findings},
        indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"states: {ok}/{len(pages)} pages read, {len(failed)} unreachable, {len(findings)} new funding links; "
          f"tracker: {len(t_find)} open windows ({t_note})")
    runlog.record("scan_states", "ok" if ok else "error",
                  note=f"{ok}/{len(pages)} pages read · {t_note}",
                  pages=len(pages), read=ok, unreachable=len(failed), new_links=len(findings),
                  tracker_open=len(t_find))


if __name__ == "__main__":
    main()
