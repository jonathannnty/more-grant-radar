#!/usr/bin/env python3
"""Weekly AI verification + discovery pass. Replaces the human Monday triage.

Three jobs, in priority order, inside one cost budget:
  1. Verify new leads (data/leads.json) against their primary pages. Verified
     opportunities become rows in data/grants.json; the rest are marked
     rejected/watch with a reason, so nothing is silently dropped.
  2. Re-check tracked rows that are due (next_check passed, the page watcher saw
     new dates, or the deadline passed within 120 days, to find the next cycle).
  3. Discovery sweep: a rotating slice of states (all 50 + DC every ~10 weeks)
     for open opioid-settlement / behavioral-health money at state, county and
     city level.

Uses Claude (Anthropic API) with the server-side web_search and web_fetch tools
and one strict client tool, submit_verdict. Every row it writes still has to
pass generate.py's validation, must cite a page Claude actually fetched (or the
scanner's own lead URL), and may not cite a known SEO-farm domain.

Needs ANTHROPIC_API_KEY. Without it the pass records "skipped: no key" in
data/runs.json, which the site shows, and exits 0.

Usage: python scripts/ai_pass.py [--today YYYY-MM-DD] [--max-usd 12] [--dry-run]
"""
import argparse
import json
import os
import re
import sys
import urllib.parse
from datetime import date, timedelta
from pathlib import Path

if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, str(Path(__file__).resolve().parent))
import runlog  # noqa: E402
from generate import validate, priority  # noqa: E402
import accelerators  # noqa: E402

STR_FIELDS = ("name", "funder", "program", "channel", "state", "path", "forprofit_direct", "category",
              "heart", "eligibility", "nofo_url", "source_url", "portal", "accounts_needed",
              "match_required", "page_limit", "attachments", "scoring_map", "kit_type", "notes")
NUM_FIELDS = ("accessible_usd", "pool_usd", "effort_hrs")


def normalize(row):
    """Coerce model output to the shapes the site code expects (strings, numbers)."""
    for k in STR_FIELDS:
        v = row.get(k)
        if isinstance(v, list):
            row[k] = "; ".join(str(x) for x in v)
        elif isinstance(v, dict):
            row[k] = "; ".join(f"{a}: {b}" for a, b in v.items())
        elif v is not None and not isinstance(v, str):
            row[k] = str(v)
    for k in NUM_FIELDS:
        v = row.get(k)
        if isinstance(v, str):
            digits = re.sub(r"[^0-9.]", "", v)
            row[k] = float(digits) if digits.count(".") == 1 else (int(digits) if digits else None)
        elif v is not None and not isinstance(v, (int, float)):
            row[k] = None
    if isinstance(row.get("likelihood"), (int, float, str)):
        try:
            row["likelihood"] = max(1, min(5, int(round(float(row["likelihood"])))))
        except ValueError:
            pass
    if isinstance(row.get("aliases"), str):
        row["aliases"] = [row["aliases"]]
    return row


def smoke(row, today):
    """Run the same per-row code the site build runs; any crash rejects the row."""
    r = dict(row)
    r["priority"] = priority(r)
    accelerators.eligibility_label(r, {"gates": {}})
    accelerators.reg_alert(r, today)
    accelerators.fit_draft(r)
    accelerators.checklist(r, today)
    json.dumps(r, ensure_ascii=False)

ROOT = Path(__file__).resolve().parents[1]
GRANTS = ROOT / "data" / "grants.json"
LEADS = ROOT / "data" / "leads.json"
FLAGS = ROOT / "data" / "row_flags.json"
PROMPT = (ROOT / "agent" / "ai_pass_prompt.md").read_text(encoding="utf-8")

# Sonnet 5.5: half Opus price; every date/amount it writes is checked against the fetched page text.
# Sonnet verifies leads and re-checks rows (comparable to Opus there, ~1/4 the cost on a
# 2026-10-21 side-by-side); Opus keeps the open-ended state sweep, where Sonnet found nothing.
MODEL = os.environ.get("AI_PASS_MODEL", "claude-sonnet-5-5")
SWEEP_MODEL = os.environ.get("AI_PASS_SWEEP_MODEL", "claude-opus-5-5")
SWEEP_RESERVE = float(os.environ.get("AI_PASS_SWEEP_RESERVE_USD", "4"))
PRICES = {"claude-sonnet-5-5": (2.0, 10.0), "claude-opus-5-5": (4.0, 20.0)}
PRICE_SEARCH = 10.0 / 1000
MAX_TURNS = 24
POISONED = ("grantfinder", "grantsights", "grantarchive", "grantwatch", "instrumentl", "grantforward")
STATES_ROTATION = ["CA", "TX", "FL", "NY", "PA", "OH", "IL", "MI", "NC", "GA", "NJ", "VA", "WA", "AZ",
                   "MA", "TN", "IN", "MO", "MD", "WI", "CO", "MN", "SC", "AL", "LA", "KY", "OR", "OK",
                   "CT", "UT", "IA", "NV", "AR", "MS", "KS", "NM", "NE", "ID", "WV", "HI", "NH", "ME",
                   "RI", "MT", "DE", "SD", "ND", "AK", "DC", "VT", "WY"]
STATES_PER_WEEK = 5
# Fields people own (or that record history): the AI pass never overwrites them.
KEEP_HUMAN = {"found_date", "kit_url", "kit_type", "subcontract_path", "award_date", "outreach_by",
              "prep_needed", "funded_list_source"}

VERDICT_TOOL = {
    "name": "submit_verdict",
    "description": ("Record your conclusion on one funding opportunity. Call once per opportunity. "
                    "row_json must be a JSON object encoded as a string (see the brief for the schema). For add/watch it MUST include "
                    "grant_id, name, funder, channel, path, heart, likelihood and source_url."),
    "strict": True,
    "input_schema": {
        "type": "object",
        "properties": {
            "decision": {"type": "string", "enum": ["add", "update", "watch", "reject"]},
            "subject": {"type": "string", "description": "lead key or grant_id this verdict is about, or 'new'"},
            "reason": {"type": "string"},
            "row_json": {"type": "string"},
        },
        "required": ["decision", "subject", "reason", "row_json"],
        "additionalProperties": False,
    },
}
SERVER_TOOLS = [
    {"type": "web_search_20260209", "name": "web_search", "max_uses": 8},
    {"type": "web_fetch_20260209", "name": "web_fetch", "max_uses": 12},
]


def domain(u):
    try:
        return urllib.parse.urlparse(u).netloc.lower()
    except ValueError:
        return ""


class Budget:
    def __init__(self, max_usd):
        self.max, self.spent = max_usd, 0.0

    def add(self, usage, model=MODEL):
        pin, pout = (x / 1e6 for x in PRICES.get(model, (4.0, 20.0)))
        if not usage:
            return
        tin = (getattr(usage, "input_tokens", 0) or 0) + (getattr(usage, "cache_creation_input_tokens", 0) or 0)
        tin += 0.1 * (getattr(usage, "cache_read_input_tokens", 0) or 0)
        tout = getattr(usage, "output_tokens", 0) or 0
        stu = getattr(usage, "server_tool_use", None)
        searches = getattr(stu, "web_search_requests", 0) if stu else 0
        self.spent += tin * pin + tout * pout + (searches or 0) * PRICE_SEARCH

    @property
    def left(self):
        return self.max - self.spent


def converse(client, budget, task, model=MODEL):
    """Run one task to completion. Returns (verdicts, fetched_urls, fetched_texts)."""
    messages = [{"role": "user", "content": task}]
    verdicts, fetched, texts = [], set(), []
    for _ in range(MAX_TURNS):
        if budget.left <= 0:
            break
        resp = client.beta.messages.create(
            model=model, max_tokens=16000,
            system=[{"type": "text", "text": PROMPT, "cache_control": {"type": "ephemeral"}}],
            tools=SERVER_TOOLS + [VERDICT_TOOL],
            output_config={"effort": "medium"},
            messages=messages,
            betas=["server-side-fallback-2026-07-01"],
            extra_body={"fallbacks": "default"},
        )
        budget.add(resp.usage, model)
        if resp.stop_reason == "refusal":
            break
        for b in resp.content:
            if b.type == "server_tool_use" and b.name == "web_fetch":
                u = (b.input or {}).get("url")
                if u:
                    fetched.add(u)
            elif b.type in ("web_fetch_tool_result", "code_execution_tool_result",
                            "bash_code_execution_tool_result"):
                texts.extend(page_texts(b.model_dump()))
        messages.append({"role": "assistant", "content": resp.content})
        if resp.stop_reason == "pause_turn":
            continue
        calls = [b for b in resp.content if b.type == "tool_use" and b.name == "submit_verdict"]
        if not calls:
            break
        results = []
        for c in calls:
            verdicts.append(dict(c.input))
            results.append({"type": "tool_result", "tool_use_id": c.id, "content": "recorded"})
        messages.append({"role": "user", "content": results})
        if resp.stop_reason == "end_turn":
            break
    return verdicts, fetched, texts


def page_texts(d):
    """Text of fetched pages inside a result block (HTML/markdown text, or a PDF's text)."""
    out = []
    c = d.get("content") or {}
    if isinstance(c, dict) and c.get("type") == "web_fetch_result":
        src = (c.get("content") or {}).get("source") or {}
        if src.get("type") == "text":
            out.append(src.get("data") or "")
        elif src.get("type") == "base64" and "pdf" in (src.get("media_type") or ""):
            try:
                import base64
                import io
                from pypdf import PdfReader
                rd = PdfReader(io.BytesIO(base64.b64decode(src["data"])))
                out.append(" ".join((pg.extract_text() or "") for pg in rd.pages[:40]))
            except Exception:
                pass
    elif isinstance(c, dict) and c.get("stdout"):
        out.append(c["stdout"])  # filtered page text the model printed via code execution
    return out


MONTHS = ["january", "february", "march", "april", "may", "june", "july", "august", "september",
          "october", "november", "december"]


def _flat(t):
    t = t.lower().replace("\\u00a0", " ").replace(" ", " ")
    t = re.sub(r"(\d)(st|nd|rd|th)\b", r"\1", t)
    t = re.sub(r"(?<=\d),(?=\d{3}\b)", "", t)  # 1,247,611 -> 1247611
    return re.sub(r"[\s,*_]+", " ", t)


def date_on_page(iso, blob):
    """True if the date appears in any common US/ISO spelling."""
    y, m, d = (int(x) for x in iso.split("-"))
    mon = MONTHS[m - 1]
    pats = [rf"\b({mon}|{mon[:3]}\.?|{mon[:4]}\.?) 0?{d} {y}\b", rf"\b0?{d} ({mon}|{mon[:3]}) {y}\b",
            rf"\b0?{m}/0?{d}/({y}|{y % 100:02d})\b", rf"\b{iso}\b", rf"\b0?{m}-0?{d}-{y}\b"]
    return any(re.search(p, blob) for p in pats)


def amount_on_page(n, blob):
    n = int(n)
    forms = {f"{n:,}", str(n)}
    if n >= 1_000_000:
        mm = f"{n / 1e6:.2f}".rstrip("0").rstrip(".")
        forms |= {f"{mm} million", f"{mm}m ", f"{mm} m "}
    if n >= 1000 and n % 1000 == 0:
        forms |= {f"{n // 1000}k", f"{n // 1000},000"}
    return any(f in blob for f in forms)


TODAY_ISO = [date.today().isoformat()]


def grounded(row, cur, texts, log):
    """Every deadline the model sets must appear on a page it fetched; unconfirmed dollar
    figures are cleared rather than shipped. Returns False to refuse the verdict."""
    blob = _flat(" ".join(texts))
    gid = row.get("grant_id") or "new"
    cw = row.get("cycle_watch")
    if cw and isinstance(cw, str) and cw[:10] < TODAY_ISO[0]:
        log.append(f"{gid}: cycle_watch {cw} is in the past, cleared")
        row["cycle_watch"] = None
    dl = row.get("deadline")
    if dl and dl != (cur or {}).get("deadline"):
        if not blob or not date_on_page(dl, blob):
            log.append(f"refused {gid}: deadline {dl} not found on any fetched page")
            return False
    for k in ("accessible_usd", "pool_usd"):
        v = row.get(k)
        if isinstance(v, (int, float)) and v and v != (cur or {}).get(k) and not amount_on_page(v, blob):
            log.append(f"{gid}: {k}={v:,.0f} not found on a fetched page, cleared")
            row[k] = None
    return True


def apply_row(src, row, today, fetched, allowed_urls, log):
    """Validate and add (or merge) a verified row. Returns grant_id or None."""
    for f in ("source_url", "nofo_url"):
        u = row.get(f) or ""
        if any(p in domain(u) for p in POISONED):
            log.append(f"refused {row.get('grant_id')}: {f} is an SEO-farm domain")
            return None
    cited = [row.get("source_url"), row.get("nofo_url")]
    ok_urls = fetched | allowed_urls
    if not any(c and (c in ok_urls or any(c.rstrip("/") == u.rstrip("/") for u in ok_urls)) for c in cited):
        log.append(f"refused {row.get('grant_id')}: cites no page that was actually fetched")
        return None
    ev = row.get("evidence") or {}
    if row.get("deadline") and not ev.get("deadline_quote"):
        log.append(f"refused {row.get('grant_id')}: deadline without a verbatim quote")
        return None
    ids = {r["grant_id"]: r for r in src["rows"]}
    cur = ids.get(row.get("grant_id"))
    if cur:
        # Merge onto the existing row: a field the model left null keeps its old value
        # (except dates, where null means "closed / not announced"), and human-owned
        # fields are never touched.
        merged = dict(cur)
        for k, v in row.items():
            if k in KEEP_HUMAN:
                continue
            if v is None and k not in ("deadline", "cycle_watch") and cur.get(k) is not None:
                continue
            merged[k] = v
        row = merged
    row = normalize(row)
    row.setdefault("aliases", [])
    row.setdefault("kit_url", None)
    row["last_verified"] = today.isoformat()
    row["next_check"] = (today + timedelta(days=7)).isoformat()
    row.setdefault("found_date", today.isoformat())
    row["verified_by"] = "ai_pass"
    errs = validate(row, today)
    if errs:
        log.append(f"refused {row.get('grant_id')}: {'; '.join(errs)}")
        return None
    try:
        smoke(row, today)
    except Exception as e:
        log.append(f"refused {row.get('grant_id')}: site build would crash ({type(e).__name__}: {e})")
        return None
    if cur:
        cur.clear()
        cur.update(row)
    else:
        src["rows"].append(row)
    return row["grant_id"]


def apply_update(src, patch, today, fetched, allowed_urls, log):
    gid = patch.get("grant_id")
    cur = next((r for r in src["rows"] if r["grant_id"] == gid), None)
    if not cur:
        log.append(f"refused update: unknown grant_id {gid!r}")
        return None
    merged = {**cur, **{k: v for k, v in patch.items() if k != "evidence"}}
    merged["evidence"] = {**(cur.get("evidence") or {}), **(patch.get("evidence") or {})}
    allowed = allowed_urls | {cur.get("source_url"), cur.get("nofo_url")} - {None}
    return apply_row(src, merged, today, fetched, allowed, log)


def parse_row(v, log):
    try:
        row = json.loads(v.get("row_json") or "{}")
        return row if isinstance(row, dict) else {}
    except json.JSONDecodeError:
        log.append(f"bad row_json for {v.get('subject')}")
        return {}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--today", default=date.today().isoformat())
    ap.add_argument("--max-usd", type=float, default=float(os.environ.get("AI_PASS_MAX_USD", "8")))
    ap.add_argument("--max-leads", type=int, default=20)
    ap.add_argument("--max-rechecks", type=int, default=10)
    ap.add_argument("--sweep-states", type=int, default=STATES_PER_WEEK)
    ap.add_argument("--dry-run", action="store_true", help="print the work list and exit")
    args = ap.parse_args()
    today = date.fromisoformat(args.today)
    TODAY_ISO[0] = today.isoformat()

    src = json.loads(GRANTS.read_text(encoding="utf-8"))
    leads_doc = json.loads(LEADS.read_text(encoding="utf-8")) if LEADS.exists() else {"leads": []}
    flags = json.loads(FLAGS.read_text(encoding="utf-8")) if FLAGS.exists() else {}

    todo_leads = [l for l in leads_doc["leads"] if l.get("status") == "new" and not l.get("ai_checked")]
    todo_leads.sort(key=lambda l: (-len(l.get("fit_terms") or []), l.get("deadline") or "9999"))
    todo_leads = todo_leads[: args.max_leads]

    def due(r):
        nc = r.get("next_check")
        dl = r.get("deadline")
        recently_closed = dl and 0 < (today - date.fromisoformat(dl)).days <= 120
        return (nc and date.fromisoformat(nc) <= today) or r["grant_id"] in flags or recently_closed
    rechecks = [r for r in src["rows"] if due(r)][: args.max_rechecks]
    week = today.isocalendar()[1]
    start = (week * STATES_PER_WEEK) % len(STATES_ROTATION)
    sweep = [STATES_ROTATION[(start + i) % len(STATES_ROTATION)] for i in range(args.sweep_states)]

    print(f"ai_pass: {len(todo_leads)} leads to verify · {len(rechecks)} rows to re-check · sweep {sweep}")
    if args.dry_run:
        for l in todo_leads:
            print("  lead", l["key"], "|", l.get("title", "")[:70])
        for r in rechecks:
            print("  recheck", r["grant_id"])
        return
    if not os.environ.get("ANTHROPIC_API_KEY"):
        runlog.record("ai_pass", "skipped", note="no ANTHROPIC_API_KEY secret: leads stay unverified",
                      pending_leads=len(todo_leads), pending_rechecks=len(rechecks))
        print("ai_pass: skipped (no ANTHROPIC_API_KEY)")
        return

    import anthropic
    client = anthropic.Anthropic()
    try:  # fail fast and loudly on a bad key instead of 35 identical errors
        client.models.retrieve(MODEL)
    except anthropic.AuthenticationError:
        runlog.record("ai_pass", "error", note="ANTHROPIC_API_KEY was rejected (401 invalid x-api-key): "
                      "re-paste the secret in GitHub Settings > Secrets > Actions",
                      pending_leads=len(todo_leads), pending_rechecks=len(rechecks))
        print("ai_pass: ANTHROPIC_API_KEY rejected (401)")
        return
    except anthropic.APIError as e:
        print(f"ai_pass: key check inconclusive ({type(e).__name__}); continuing")
    budget = Budget(args.max_usd)
    log, added, updated, rejected, watched, errors = [], [], [], 0, 0, 0
    tracked = sorted(r["grant_id"] for r in src["rows"])

    def checkpoint():
        GRANTS.write_text(json.dumps(src, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
        LEADS.write_text(json.dumps(leads_doc, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")

    def handle(verdicts, fetched, allowed, lead=None, texts=()):
        nonlocal rejected, watched
        outcome = None
        cur_by_id = {r["grant_id"]: r for r in src["rows"]}
        for v in verdicts:
            row = parse_row(v, log)
            d = v.get("decision")
            if row and d in ("add", "update", "watch"):
                row = normalize(row)
                if not grounded(row, cur_by_id.get(row.get("grant_id")), texts, log):
                    continue
            if d == "add" and row:
                existed = row.get("grant_id") in {r["grant_id"] for r in src["rows"]}
                gid = apply_row(src, row, today, fetched, allowed, log)
                if gid:
                    (updated if existed else added).append(gid)
                    outcome = ("promoted", f"verified as {gid}")
            elif d == "update" and row:
                gid = apply_update(src, row, today, fetched, allowed, log)
                if gid:
                    updated.append(gid)
                    outcome = outcome or ("promoted", f"merged into {gid}")
            elif d == "watch":
                watched += 1
                if row.get("grant_id") and row.get("source_url"):
                    row.setdefault("deadline", None)
                    gid = apply_row(src, row, today, fetched, allowed, log)
                    if gid:
                        added.append(gid)
                        outcome = outcome or ("promoted", f"watching as {gid}")  # don't also list it as a lead
                outcome = outcome or ("watch", v.get("reason", "")[:200])
            elif d == "reject":
                rejected += 1
                outcome = outcome or ("rejected", v.get("reason", "")[:200])
        checkpoint()
        if lead is not None:
            lead["ai_checked"] = today.isoformat()
            if outcome:
                st, note = outcome
                lead["status"] = "new" if st == "watch" else st
                lead["status_note"] = note

    # 1. leads
    for l in todo_leads:
        if budget.left <= SWEEP_RESERVE:  # keep money for the state sweep
            break
        hint = ("\nNOTE: grants.gov detail pages need JavaScript and usually fail to fetch. The LEAD below already "
                "holds the official grants.gov API record (deadline, ceiling, applicant types, synopsis); you may "
                "cite its url as the source. For the full text fetch the agency's NOFO (nofo_url, or the NIH Guide / "
                "bja.ojp.gov / hrsa.gov / samhsa.gov announcement) or simpler.grants.gov/search?query=<number>.\n"
                if l.get("source") == "grants_gov" else "")
        task = (f"Today is {today}. Verify this machine-found lead against its primary source and decide.{hint}\n"
                f"Already tracked grant_ids (do not duplicate; use `update` if it is one of these): "
                f"{', '.join(tracked)}\n\nLEAD:\n{json.dumps(l, ensure_ascii=False, indent=1)}")
        try:
            verdicts, fetched, texts = converse(client, budget, task)
            if l.get("source") == "grants_gov":  # the scanner's official API record is primary evidence
                texts = texts + [json.dumps(l, ensure_ascii=False), l.get("deadline_quote") or ""]
            handle(verdicts, fetched, {l.get("url"), l.get("nofo_url")} - {None}, lead=l, texts=texts)
        except anthropic.APIError as e:
            errors += 1
            log.append(f"lead {l['key']}: {type(e).__name__}: {str(e)[:120]}")

    # 2. re-checks
    for r in rechecks:
        if budget.left <= SWEEP_RESERVE:  # keep money for the state sweep
            break
        why = ("the page watcher saw new dates: " + ", ".join(flags[r["grant_id"]]["added_dates"])
               if r["grant_id"] in flags else "scheduled re-verification")
        task = (f"Today is {today}. Re-verify this tracked row ({why}). If its cycle closed, look for the NEXT "
                f"cycle on the funder's own site and `update` the row to describe it (or `watch` with cycle_watch). "
                f"If nothing changed, `update` with only grant_id and evidence (that refreshes last_verified).\n\n"
                f"ROW:\n{json.dumps(r, ensure_ascii=False, indent=1)}")
        try:
            verdicts, fetched, texts = converse(client, budget, task)
            handle(verdicts, fetched, {r.get("source_url"), r.get("nofo_url")} - {None}, texts=texts)
        except anthropic.APIError as e:
            errors += 1
            log.append(f"recheck {r['grant_id']}: {type(e).__name__}: {str(e)[:120]}")

    # 3. discovery sweep
    dirmap = {s["state"]: s for s in src.get("state_directory", [])}
    names = {v: k for k, v in __import__("scan_states").STATES.items()}
    for code in sweep:
        if budget.left <= 0:
            break
        d = dirmap.get(names.get(code, ""), {})
        task = (f"Today is {today}. Discovery sweep for {names.get(code, code)} ({code}). Find funding that is OPEN "
                f"now or concretely upcoming for MORE clinician training: the state opioid settlement / abatement "
                f"body, the state behavioral-health agency's RFPs/RFAs, and the largest counties and cities' opioid "
                f"settlement grant programs. Known starting pages: {d.get('url')} · {d.get('settlement_url')}. "
                f"Submit a verdict for each opportunity you verify (add or watch); skip anything closed. "
                f"Do not duplicate tracked grant_ids: {', '.join(tracked)}")
        try:
            verdicts, fetched, texts = converse(client, budget, task, model=SWEEP_MODEL)
            handle(verdicts, fetched, set(), texts=texts)
        except anthropic.APIError as e:
            errors += 1
            log.append(f"sweep {code}: {type(e).__name__}: {str(e)[:120]}")

    GRANTS.write_text(json.dumps(src, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    LEADS.write_text(json.dumps(leads_doc, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    note = f"{MODEL} + {SWEEP_MODEL} sweep · ${budget.spent:.2f} spent · swept {','.join(sweep)}"
    if log:
        note += " · " + " | ".join(log[:6])
    runlog.record("ai_pass", "ok" if not errors else "partial", note=note[:900],
                  added=len(set(added)), updated=len(set(updated)), rejected=rejected, watch=watched,
                  errors=errors, swept=len(sweep))
    print(f"ai_pass: +{len(set(added))} rows, {len(set(updated))} updated, {rejected} rejected, "
          f"{watched} watch, {errors} errors, ${budget.spent:.2f}")
    for line in log:
        print("  ", line)


if __name__ == "__main__":
    main()
