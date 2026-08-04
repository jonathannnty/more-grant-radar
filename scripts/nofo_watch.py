#!/usr/bin/env python3
"""NOFO change detection (radar v2, item 3b).

Fetches each tracked opportunity's primary page, fingerprints it, and reports
NEW / CHANGED / UNREACHABLE against the last snapshot (data/nofo_snapshots.json).
Amendments and deadline extensions happen (Alabama R4, Allegheny OSF both ran
amended RFPs) — this catches them between full re-verifications. Flags for a
human to verify; it never edits a verified field.

Run from a machine with network (Claude Code on Ty's box).
Usage: python scripts/nofo_watch.py [--update]   # --update writes the new baseline
"""
import argparse
import hashlib
import json
import re
import sys
import urllib.request
from datetime import date
from pathlib import Path

if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parents[1]
SNAP = ROOT / "data" / "nofo_snapshots.json"
UA = "Mozilla/5.0 (MORE Grant Radar NOFO watch)"


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=45) as r:
        raw = r.read(600_000).decode("utf-8", "replace")
    text = re.sub(r"<script[\s\S]*?</script>|<style[\s\S]*?</style>", " ", raw, flags=re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip().lower()
    return text


def fingerprint(text):
    # date-like tokens are the highest-signal change; keep a sorted set + a content hash
    dates = sorted(set(re.findall(r"\b\d{1,2}/\d{1,2}/\d{2,4}\b|\b(?:january|february|march|april|may|june|july|"
                                  r"august|september|october|november|december)\s+\d{1,2},?\s+\d{4}\b", text)))
    return {"hash": hashlib.sha256(text.encode()).hexdigest()[:16], "len": len(text), "dates": dates[:40]}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--update", action="store_true", help="write the fetched fingerprints as the new baseline")
    args = ap.parse_args()

    rows = json.loads((ROOT / "data" / "grants.json").read_text(encoding="utf-8"))["rows"]
    old = json.loads(SNAP.read_text(encoding="utf-8")) if SNAP.exists() else {}
    new, changes = {}, []

    for r in rows:
        url = r.get("nofo_url") or r.get("source_url")
        if not url:
            continue
        gid = r["grant_id"]
        try:
            fp = fingerprint(fetch(url))
        except Exception as e:
            changes.append(("UNREACHABLE", gid, f"{type(e).__name__}: {str(e)[:60]}", url))
            new[gid] = old.get(gid, {})  # keep prior baseline
            continue
        new[gid] = {**fp, "url": url}
        prev = old.get(gid)
        if not prev:
            changes.append(("NEW", gid, "no prior snapshot — baseline set", url))
        elif prev.get("hash") != fp["hash"]:
            added = sorted(set(fp["dates"]) - set(prev.get("dates", [])))
            removed = sorted(set(prev.get("dates", [])) - set(fp["dates"]))
            detail = "content changed"
            if added or removed:
                detail += f" · dates +{added[:4]} -{removed[:4]}"
            changes.append(("CHANGED", gid, detail, url))

    print(f"NOFO watch — {date.today()} · {len(new)} pages checked\n" + "=" * 70)
    order = {"CHANGED": 0, "UNREACHABLE": 1, "NEW": 2}
    for kind, gid, detail, url in sorted(changes, key=lambda c: order[c[0]]):
        print(f"  [{kind:11}] {gid:30} {detail}")
        if kind in ("CHANGED", "UNREACHABLE"):
            print(f"                {url}")
    if not any(c[0] == "CHANGED" for c in changes):
        print("  no content changes vs the last snapshot.")

    if args.update or not SNAP.exists():
        SNAP.write_text(json.dumps(new, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"\n  ✓ baseline written to {SNAP.relative_to(ROOT)}")
    else:
        print("\n  (run with --update to save this as the new baseline)")


if __name__ == "__main__":
    main()
