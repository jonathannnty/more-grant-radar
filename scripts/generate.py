#!/usr/bin/env python3
"""MORE Grant Radar — engine generator.

Reads data/grants.json (engine-owned source of truth) and emits:
  data/radar.csv          exact Data_Auto schema, engine-sorted (act-now band by
                          deadline, then priority desc) — the Sheet imports this
  data/archive.csv        expired/decided rows, appended with a reason (never deleted)
  ics/<grant_id>.ics      all-day deadline event with a -3 day alarm, per dated row
  site/index.html         template.html with the data payload injected
  apps_script/setup.gs    seed CSV + state directory injected between markers

Non-negotiables enforced here: every row needs a primary source URL and a
last_verified stamp; expired rows move to the archive with a reason; humans own
Team, this file owns Data_Auto.

Usage: python scripts/generate.py [--today YYYY-MM-DD]
"""
import argparse
import csv
import io
import json
import math
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parents[1]

COLS = [
    "grant_id", "name", "funder", "program", "channel", "state", "path",
    "forprofit_direct", "category", "accessible_usd", "pool_usd", "deadline",
    "cycle_watch", "likelihood", "priority", "heart", "nofo_url", "source_url",
    "portal", "accounts_needed", "match_required", "page_limit", "attachments",
    "scoring_map", "effort_hrs", "kit_type", "kit_url", "last_verified",
    "next_check", "found_date",
]

DATE_FIELDS = ["deadline", "cycle_watch", "last_verified", "next_check", "found_date"]
DIR_COLS = ["state", "agency", "url", "settlement_url", "notes"]


def parse_date(v):
    if not v:
        return None
    return date.fromisoformat(str(v))


def validate(row, today):
    errors = []
    for req in ("grant_id", "name", "funder", "channel", "path", "heart"):
        if not row.get(req):
            errors.append(f"missing {req}")
    if not (row.get("nofo_url") or row.get("source_url")):
        errors.append("no primary source URL (nofo_url/source_url)")
    if not row.get("last_verified"):
        errors.append("no last_verified stamp — a row may not enter Data_Auto unverified")
    lk = row.get("likelihood")
    if not isinstance(lk, (int, float)) or not 1 <= lk <= 5:
        errors.append(f"likelihood must be 1-5, got {lk!r}")
    for f in DATE_FIELDS:
        if row.get(f):
            try:
                parse_date(row[f])
            except ValueError:
                errors.append(f"{f} is not YYYY-MM-DD: {row[f]!r}")
    for f in ("accessible_usd", "pool_usd", "effort_hrs"):
        if row.get(f) is not None and not isinstance(row[f], (int, float)):
            errors.append(f"{f} must be a number or null, got {row[f]!r}")
    return errors


def priority(row):
    acc = row.get("accessible_usd") or 10
    return round(row["likelihood"] * math.log10(max(acc, 10)), 1)


def sort_rows(rows, today):
    act, watch = [], []
    for r in rows:
        d = parse_date(r.get("deadline"))
        if d and 0 <= (d - today).days <= 45:
            act.append(r)
        else:
            watch.append(r)
    act.sort(key=lambda r: r["deadline"])
    watch.sort(key=lambda r: r["priority"], reverse=True)
    return act + watch


def csv_text(rows, cols):
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=cols, extrasaction="ignore", lineterminator="\n")
    w.writeheader()
    for r in rows:
        w.writerow({c: ("" if r.get(c) is None else r.get(c)) for c in cols})
    return buf.getvalue()


def write_ics(row, out_dir):
    d = row["deadline"].replace("-", "")
    title = f"{row['name']} due — MORE Grant Radar"
    uid = f"{row['grant_id']}-{d}@more-grant-radar"
    ics = "\r\n".join([
        "BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//MORE Grant Radar//EN",
        "BEGIN:VEVENT", f"UID:{uid}",
        f"DTSTAMP:{date.today().strftime('%Y%m%d')}T120000Z",
        f"DTSTART;VALUE=DATE:{d}", f"SUMMARY:{title}",
        f"URL:{row.get('nofo_url') or row.get('source_url')}",
        "BEGIN:VALARM", "TRIGGER:-P3D", "ACTION:DISPLAY",
        f"DESCRIPTION:{title}", "END:VALARM",
        "END:VEVENT", "END:VCALENDAR", "",
    ])
    (out_dir / f"{row['grant_id']}.ics").write_text(ics, encoding="utf-8")


def load_team(path):
    """Optional data/team.csv (exported from the Sheet's Team tab) overlays
    status/owner/next_action onto the site. Humans own that data; we only read it."""
    if not path.exists():
        return {}
    with path.open(encoding="utf-8-sig", newline="") as f:
        return {r["grant_id"].strip(): r for r in csv.DictReader(f) if r.get("grant_id")}


def inject(path, start, end, payload, label):
    text = path.read_text(encoding="utf-8")
    i, j = text.find(start), text.find(end)
    if i == -1 or j == -1:
        print(f"  ! marker {start!r} not found in {path.name} — skipped {label}")
        return
    path.write_text(text[: i + len(start)] + "\n" + payload + "\n" + text[j:], encoding="utf-8")
    print(f"  ✓ {label} → {path.relative_to(ROOT)}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--today", default=date.today().isoformat())
    args = ap.parse_args()
    today = date.fromisoformat(args.today)

    src = json.loads((ROOT / "data" / "grants.json").read_text(encoding="utf-8"))
    rows, coverage = src["rows"], src.get("coverage", [])

    # Validate — a bad row stops the build rather than shipping bad data.
    failed = False
    for r in rows:
        errs = validate(r, today)
        if errs:
            failed = True
            print(f"INVALID {r.get('grant_id', '<no id>')}: {'; '.join(errs)}")
    if failed:
        sys.exit("Aborting: fix data/grants.json (nothing was written).")

    # Expire → archive with a reason, never silent deletion.
    active, expired = [], []
    for r in rows:
        d = parse_date(r.get("deadline"))
        if d and d < today:
            expired.append(r)
        else:
            active.append(r)
    if expired:
        arch = ROOT / "data" / "archive.csv"
        new_file = not arch.exists()
        with arch.open("a", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=COLS + ["archived_on", "reason"], extrasaction="ignore", lineterminator="\n")
            if new_file:
                w.writeheader()
            for r in expired:
                w.writerow({**{c: r.get(c, "") for c in COLS}, "archived_on": today.isoformat(), "reason": "expired"})
        ids = ", ".join(r["grant_id"] for r in expired)
        print(f"  → archived {len(expired)} expired row(s): {ids}")

    for r in active:
        r["priority"] = priority(r)
    active = sort_rows(active, today)

    # Freshness check (warn — the Monday sync fixes these).
    for r in active:
        age = (today - parse_date(r["last_verified"])).days
        if age > 7:
            print(f"  ⚠ stale: {r['grant_id']} last verified {age}d ago")

    # radar.csv
    radar_csv = csv_text(active, COLS)
    (ROOT / "data" / "radar.csv").write_text(radar_csv, encoding="utf-8")
    print(f"  ✓ data/radar.csv — {len(active)} rows")

    # .ics per dated row
    ics_dir = ROOT / "ics"
    ics_dir.mkdir(exist_ok=True)
    for old in ics_dir.glob("*.ics"):
        old.unlink()
    dated = [r for r in active if r.get("deadline")]
    for r in dated:
        write_ics(r, ics_dir)
    print(f"  ✓ ics/ — {len(dated)} calendar file(s)")

    # Site — template + payload (+ optional Team overlay for status/owner)
    team = load_team(ROOT / "data" / "team.csv")
    site_rows = []
    for r in active:
        t = team.get(r["grant_id"], {})
        site_rows.append({**r, "status": t.get("status") or "New", "owner": t.get("owner") or "",
                          "next_action": t.get("next_action") or ""})
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    payload = "const RADAR = " + json.dumps(
        {"today": today.isoformat(), "rows": site_rows, "coverage": coverage},
        ensure_ascii=False) + ";"
    html = (ROOT / "site" / "template.html").read_text(encoding="utf-8")
    html = html.replace("/*__RADAR_DATA__*/", payload).replace("__BUILD_STAMP__", stamp)
    (ROOT / "site" / "index.html").write_text(html, encoding="utf-8")
    print("  ✓ site/index.html")

    # Apps Script seed payload
    gs = ROOT / "apps_script" / "setup.gs"
    if gs.exists():
        inject(gs, "// <<RADAR_CSV>>", "// <<END_RADAR_CSV>>",
               "var SEED_RADAR_CSV = " + json.dumps(radar_csv) + ";", "seed CSV")
        directory = src.get("state_directory", [])
        dir_csv = csv_text(directory, DIR_COLS) if directory else ""
        inject(gs, "// <<DIRECTORY_CSV>>", "// <<END_DIRECTORY_CSV>>",
               "var STATE_DIRECTORY_CSV = " + json.dumps(dir_csv) + ";", "state directory")

    hot = [r for r in active if r.get("deadline") and (parse_date(r["deadline"]) - today).days <= 14]
    print(f"Done. {len(active)} active rows · {len(hot)} inside 14 days" +
          (f" ({', '.join(r['grant_id'] for r in hot)})" if hot else ""))


if __name__ == "__main__":
    main()
