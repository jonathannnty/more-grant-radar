#!/usr/bin/env python3
"""Email alerts for the radar (Resend), sent from radar@moretherapy.com.

Three kinds of email, each sent at most once per item:
  * Deadline alert (any day): a verified opportunity found in the last 3 days whose
    deadline or outreach window is within 30 days.
  * Problem alert (any day): a radar job is overdue or failing (same check as the
    site's banner), so a stall can never go unnoticed again. Repeats every 3 days
    while the problem lasts.
  * Weekly digest (Mondays, after the AI pass, or --digest): new opportunities this
    week, deadlines in the next 21 days, leads awaiting verification, radar health.
    On digest days the deadline alert is folded into the digest.

Config (environment):
  RESEND_API_KEY   Resend API key (GitHub secret). Missing: records "skipped", exits 0.
  RADAR_EMAIL_TO   comma-separated recipients (GitHub secret: the repo is public).
  RADAR_EMAIL_FROM default "MORE Grant Radar <radar@moretherapy.com>"
  RADAR_SITE_URL   default the GitHub Pages site

State: data/notify_state.json (grant ids and dates only, no addresses).

Usage: python scripts/notify.py [--today YYYY-MM-DD] [--digest] [--test] [--preview DIR]
  --test     send a one-off test email now (ignores state)
  --preview  write the emails that would be sent as .html files to DIR, send nothing
"""
import argparse
import html
import json
import os
import sys
import urllib.error
import urllib.request
from datetime import date, timedelta
from pathlib import Path

if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, str(Path(__file__).resolve().parent))
import runlog  # noqa: E402
from generate import build_health, effective_date, effective_expiry, priority, validate  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT / "data" / "notify_state.json"
SITE = os.environ.get("RADAR_SITE_URL", "https://jonathannnty.github.io/more-grant-radar/")
FROM = os.environ.get("RADAR_EMAIL_FROM", "MORE Grant Radar <radar@moretherapy.com>")
API = "https://api.resend.com/emails"
ALERT_WINDOW_DAYS = 30
NEW_WINDOW_DAYS = 3
HEALTH_REPEAT_DAYS = 3

INK, MUTED, RULE, ACCENT, RED, AMBER = "#1d2433", "#5b6475", "#e3e6ec", "#2f55c6", "#c0392b", "#9a6b00"


def esc(s):
    return html.escape(str(s or ""))


def money(n):
    if not n:
        return ""
    return f"${n / 1e6:.1f}M".replace(".0M", "M") if n >= 1e6 else f"${n / 1e3:.0f}K" if n >= 1e3 else f"${n:,.0f}"


def fmt(d):
    return d.strftime("%a %b %-d") if os.name != "nt" else d.strftime("%a %b %#d")


def load_state():
    try:
        return json.loads(STATE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def active_rows(today):
    src = json.loads((ROOT / "data" / "grants.json").read_text(encoding="utf-8"))
    rows = []
    for r in src["rows"]:
        if validate(r, today):
            continue
        exp = effective_expiry(r)
        if exp and exp < today:
            continue
        r["priority"] = priority(r)
        rows.append(r)
    return rows


def due_line(r, today):
    d = effective_date(r)
    if d:
        days = (d - today).days
        what = "outreach by" if r.get("subcontract_path") and r.get("outreach_by") else "due"
        color = RED if days <= 14 else AMBER if days <= 45 else MUTED
        return f'<span style="color:{color};font-weight:600">{what} {fmt(d)} · {days}d</span>'
    if r.get("cycle_watch"):
        return f'<span style="color:{MUTED}">watch {date.fromisoformat(r["cycle_watch"]).strftime("%b %Y")}</span>'
    return f'<span style="color:{MUTED}">date not announced</span>'


def row_block(r, today):
    link = r.get("nofo_url") or r.get("source_url") or SITE
    meta = " · ".join(x for x in [r.get("funder"), r.get("state") if r.get("state") != "US" else "national",
                                  r.get("path"), money(r.get("accessible_usd"))] if x)
    return (f'<tr><td style="padding:12px 0;border-top:1px solid {RULE}">'
            f'<div style="font-size:15px;font-weight:600;color:{INK}">{esc(r["name"])}</div>'
            f'<div style="font-size:12px;color:{MUTED};margin:2px 0 6px">{esc(meta)}</div>'
            f'<div style="font-size:13px;color:{INK};line-height:1.45">{esc(r.get("heart"))}</div>'
            f'<div style="font-size:13px;margin-top:6px">{due_line(r, today)} &nbsp;·&nbsp; '
            f'<a href="{esc(link)}" style="color:{ACCENT}">funder page</a></div></td></tr>')


def section(title, rows, today, empty=None):
    if not rows and not empty:
        return ""
    body = "".join(row_block(r, today) for r in rows) if rows else (
        f'<tr><td style="padding:8px 0;color:{MUTED};font-size:13px">{esc(empty)}</td></tr>')
    return (f'<h2 style="font-size:13px;letter-spacing:.06em;text-transform:uppercase;color:{MUTED};'
            f'margin:24px 0 4px">{esc(title)}</h2><table width="100%" cellpadding="0" cellspacing="0">{body}</table>')


def wrap(heading, intro, inner):
    return ('<!doctype html><html><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width,initial-scale=1"></head><body>'
            f'<div style="font-family:-apple-system,Segoe UI,Helvetica,Arial,sans-serif;max-width:640px;'
            f'margin:0 auto;padding:8px 4px;color:{INK}">'
            f'<div style="font-size:11px;letter-spacing:.12em;color:{ACCENT};font-weight:700">MORE THERAPY · GRANT RADAR</div>'
            f'<h1 style="font-size:22px;margin:4px 0 8px">{esc(heading)}</h1>'
            f'<p style="font-size:14px;color:{MUTED};margin:0 0 8px;line-height:1.5">{intro}</p>{inner}'
            f'<p style="margin:28px 0 0"><a href="{SITE}" style="background:{ACCENT};color:#fff;text-decoration:none;'
            f'padding:10px 16px;border-radius:6px;font-weight:600;font-size:14px">Open the radar</a></p>'
            f'<p style="font-size:11px;color:{MUTED};margin-top:24px;line-height:1.5">Sent automatically by the MORE Grant '
            f'Radar. Every date and dollar figure is quoted from the funder\'s own page; confirm on that page before '
            f'acting. Assign owners and statuses in the Team sheet.</p></div></body></html>')


def text_of(rows, today):
    out = []
    for r in rows:
        d = effective_date(r)
        out.append(f"- {r['name']} ({r.get('funder', '')})" + (f" - due {d.isoformat()}" if d else "")
                   + f"\n  {r.get('nofo_url') or r.get('source_url') or ''}")
    return "\n".join(out)


def build_alert(new_urgent, today):
    n = len(new_urgent)
    subj = (f"Grant radar: {new_urgent[0]['name'][:70]} (due in {(effective_date(new_urgent[0]) - today).days} days)"
            if n == 1 else f"Grant radar: {n} new opportunities with deadlines in the next {ALERT_WINDOW_DAYS} days")
    intro = ("The radar just verified " + ("an opportunity" if n == 1 else f"{n} opportunities") +
             f" with a deadline inside {ALERT_WINDOW_DAYS} days. If one fits, assign an owner in the Team sheet today.")
    html_ = wrap("New and due soon", intro, section("Due soon", new_urgent, today))
    return subj, html_, f"{intro}\n\n{text_of(new_urgent, today)}\n\n{SITE}"


def build_health_alert(bad):
    lines = [f"{h['label']}: " + (f"skipped ({h['note']})" if h["status"] == "skipped" else
                                  f"last ran {h['last'][:10]}" if h["last"] else "never ran") for h in bad]
    intro = ("One or more radar jobs stopped or failed. The site may be missing new opportunities until this is fixed. "
             "Check the Actions tab of the more-grant-radar repository on GitHub.")
    inner = "<ul style='font-size:14px;line-height:1.6'>" + "".join(f"<li>{esc(l)}</li>" for l in lines) + "</ul>"
    return "Grant radar needs attention", wrap("Radar needs attention", esc(intro), inner), intro + "\n\n" + "\n".join(lines)


def build_digest(rows, today, health):
    week_ago = today - timedelta(days=7)
    new = sorted([r for r in rows if r.get("found_date") and date.fromisoformat(r["found_date"]) > week_ago],
                 key=lambda r: -r["priority"])
    soon = sorted([r for r in rows if effective_date(r) and 0 <= (effective_date(r) - today).days <= 21],
                  key=lambda r: effective_date(r))
    leads = json.loads((ROOT / "data" / "leads.json").read_text(encoding="utf-8")).get("leads", []) \
        if (ROOT / "data" / "leads.json").exists() else []
    open_leads = sum(1 for l in leads if l.get("status") == "new")
    bad = [h for h in health if not h["ok"] and h["phase"] not in ("winners", "notify")]
    states = sorted({r.get("state") for r in new if r.get("state") and r.get("state") != "US"})
    intro = (f"{len(new)} new opportunit{'y' if len(new) == 1 else 'ies'} this week"
             + (f", including state and local money in {', '.join(states)}" if states else "")
             + f". {len(soon)} deadline{'s' if len(soon) != 1 else ''} in the next 3 weeks. "
             f"{len(rows)} opportunities tracked, {open_leads} new leads awaiting verification.")
    health_html = (f'<p style="font-size:13px;color:{RED if bad else "#2e7d4f"};margin-top:20px">'
                   + (("⚠ Needs attention: " + esc(", ".join(h["label"] for h in bad))) if bad
                      else "✓ All radar jobs ran on schedule this week.") + "</p>")
    inner = (section("Deadlines in the next 3 weeks", soon, today, empty="Nothing due in the next 3 weeks.")
             + section("New this week", new[:15], today, empty="No new verified opportunities this week.")
             + (f'<p style="font-size:12px;color:{MUTED}">…and {len(new) - 15} more on the site.</p>' if len(new) > 15 else "")
             + health_html)
    subj = f"Grant radar weekly: {len(new)} new, {len(soon)} due in 3 weeks"
    text = (f"{intro}\n\nDUE IN 3 WEEKS\n{text_of(soon, today) or '(none)'}\n\nNEW THIS WEEK\n"
            f"{text_of(new[:15], today) or '(none)'}\n\n{SITE}")
    return subj, wrap(f"Week of {today.strftime('%b %-d' if os.name != 'nt' else '%b %#d')}", esc(intro), inner), text


def send(key, to, subject, html_, text):
    body = json.dumps({"from": FROM, "to": to, "subject": subject, "html": html_, "text": text}).encode()
    req = urllib.request.Request(API, data=body, method="POST", headers={
        "Authorization": f"Bearer {key}", "Content-Type": "application/json",
        "User-Agent": "more-grant-radar/4 (+https://github.com/jonathannnty/more-grant-radar)"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r).get("id")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--today", default=date.today().isoformat())
    ap.add_argument("--digest", action="store_true")
    ap.add_argument("--test", action="store_true")
    ap.add_argument("--preview", metavar="DIR")
    args = ap.parse_args()
    today = date.fromisoformat(args.today)
    key = os.environ.get("RESEND_API_KEY", "").strip()
    to = [a.strip() for a in os.environ.get("RADAR_EMAIL_TO", "").split(",") if a.strip()]

    if not args.preview and (not key or not to):
        missing = " and ".join(x for x, ok in (("RESEND_API_KEY", key), ("RADAR_EMAIL_TO", to)) if not ok)
        runlog.record("notify", "skipped", note=f"email alerts off: no {missing} secret")
        print(f"notify: skipped (no {missing})")
        return

    rows = active_rows(today)
    health = build_health(today)
    state = load_state()
    alerted = state.setdefault("alerted", {})
    health_sent = state.setdefault("health_alerted", {})
    outbox = []

    if args.test:
        outbox.append(("test",) + build_digest(rows, today, health))
    else:
        recent = today - timedelta(days=NEW_WINDOW_DAYS)
        urgent = [r for r in rows if r["grant_id"] not in alerted
                  and r.get("found_date") and date.fromisoformat(r["found_date"]) >= recent
                  and effective_date(r) and 0 <= (effective_date(r) - today).days <= ALERT_WINDOW_DAYS]
        urgent.sort(key=lambda r: effective_date(r))
        digest_day = args.digest or today.isoweekday() == 1
        if digest_day and state.get("digest_sent") != today.isoformat():
            outbox.append(("digest",) + build_digest(rows, today, health))
        elif urgent:
            outbox.append(("alert",) + build_alert(urgent, today))
        bad = [h for h in health if not h["ok"] and h["phase"] not in ("winners", "notify")]
        due_bad = [h for h in bad if not health_sent.get(h["phase"]) or
                   (today - date.fromisoformat(health_sent[h["phase"]])).days >= HEALTH_REPEAT_DAYS]
        if due_bad:
            outbox.append(("health",) + build_health_alert(bad))

    if args.preview:
        out = Path(args.preview)
        out.mkdir(parents=True, exist_ok=True)
        for kind, subj, html_, _ in outbox:
            (out / f"{kind}.html").write_text(f"<!-- {subj} -->\n{html_}", encoding="utf-8")
            print(f"preview {kind}: {subj}")
        if not outbox:
            print("preview: nothing to send today")
        return

    sent, errors = [], []
    for kind, subj, html_, text in outbox:
        try:
            send(key, to, subj, html_, text)
            sent.append(kind)
        except urllib.error.HTTPError as e:
            errors.append(f"{kind}: HTTP {e.code} {e.read().decode('utf-8', 'replace')[:160]}")
            continue
        except Exception as e:  # network etc.: record, never fail the radar
            errors.append(f"{kind}: {type(e).__name__}: {str(e)[:120]}")
            continue
        if kind == "digest":
            state["digest_sent"] = today.isoformat()
        if kind in ("digest", "alert"):
            for r in rows:  # everything currently due-soon counts as announced
                if effective_date(r) and 0 <= (effective_date(r) - today).days <= ALERT_WINDOW_DAYS:
                    alerted.setdefault(r["grant_id"], today.isoformat())
        if kind == "health":
            for h in build_health(today):
                if not h["ok"]:
                    health_sent[h["phase"]] = today.isoformat()
    if not args.test:
        live = {r["grant_id"] for r in rows}
        state["alerted"] = {k: v for k, v in alerted.items() if k in live}
        STATE.write_text(json.dumps(state, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    status = "error" if errors and not sent else "partial" if errors else "ok"
    runlog.record("notify", status, note=" | ".join(errors)[:400], sent=len(sent), recipients=len(to))
    print(f"notify: sent {sent or 'nothing'}" + (f"; errors: {errors}" if errors else ""))


if __name__ == "__main__":
    main()
