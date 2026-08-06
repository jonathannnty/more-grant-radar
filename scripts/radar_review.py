#!/usr/bin/env python3
"""Radar review aggregator (self-updating radar, Phase 2 fan-in).

Reads every findings JSON emitted by the detection scanners (grants_gov, sam,
nofo_watch, winners), dedups each finding against data/seen_finds.json, and — if
anything new survives — composes a GitHub Issue body queuing the deltas for a
human to verify against the primary source. Never touches data/grants.json.

The dedup key is ``f"{source}:{kind}:{id}:{fingerprint}"`` so a *later, different*
change to the same NOFO re-surfaces (its content fingerprint moves).

Emits ``has_findings`` and (when there are deltas) ``title`` to $GITHUB_OUTPUT so
the workflow can gate ``gh issue create`` on them; the same lines print to stdout
so a local run is legible too. The working-copy seen list is updated in place —
the workflow commits it only after the issue is created.

Usage:
  python scripts/radar_review.py --finds finds/ [--seen data/seen_finds.json] \
      --out issue_body.md [--today 2026-08-05]
"""
import argparse
import sys
if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import json
import os
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Sections render in this order; unknown sources fall in afterwards (sorted).
SOURCE_ORDER = ["grants_gov", "sam", "nofo_watch", "winners"]
SOURCE_LABEL = {
    "grants_gov": "Grants.gov",
    "sam": "SAM.gov",
    "nofo_watch": "NOFO watch",
    "winners": "Winners",
}
FOOTER = "Confirm against the primary source before adding to `grants.json`."
BODY_CAP = 60000  # keep the composed body well under GitHub's 65,536-char issue limit


def emit(pairs):
    """Write name=value lines to $GITHUB_OUTPUT (if set) and always to stdout."""
    lines = [f"{k}={v}" for k, v in pairs]
    gh_out = os.environ.get("GITHUB_OUTPUT")
    if gh_out:
        try:
            with open(gh_out, "a", encoding="utf-8") as f:
                f.write("\n".join(lines) + "\n")
        except OSError as e:
            print(f"  ! could not write $GITHUB_OUTPUT ({gh_out}): {e}", file=sys.stderr)
    for ln in lines:
        print(ln)


def load_seen(path):
    """Load the seen-key list; [] if the file is missing or unreadable."""
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as e:
        print(f"  ! seen file {path} unreadable ({e}); starting from empty.", file=sys.stderr)
        return []
    if not isinstance(data, list):
        print(f"  ! seen file {path} is not a JSON list; starting from empty.", file=sys.stderr)
        return []
    return [str(k) for k in data]


def read_finds(finds_dir):
    """Yield (source, finding) for every valid finding across *.json in finds_dir.

    Malformed or off-contract files are skipped with a warning, never fatal.
    """
    if not finds_dir.exists():
        print(f"  ! finds dir {finds_dir} does not exist; no findings to review.", file=sys.stderr)
        return
    for fp in sorted(finds_dir.glob("*.json")):
        try:
            doc = json.loads(fp.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as e:
            print(f"  ! skipping {fp.name}: unreadable ({e}).", file=sys.stderr)
            continue
        if not isinstance(doc, dict):
            print(f"  ! skipping {fp.name}: top level is not an object.", file=sys.stderr)
            continue
        source = doc.get("source")
        findings = doc.get("findings")
        if not isinstance(source, str) or not source:
            print(f"  ! skipping {fp.name}: missing/invalid 'source'.", file=sys.stderr)
            continue
        if not isinstance(findings, list):
            print(f"  ! skipping {fp.name}: 'findings' is not a list.", file=sys.stderr)
            continue
        for fnd in findings:
            if not isinstance(fnd, dict):
                print(f"  ! {fp.name}: skipping a finding that is not an object.", file=sys.stderr)
                continue
            kind = fnd.get("kind")
            fid = fnd.get("id")
            if not kind or fid is None or fid == "":
                print(f"  ! {fp.name}: skipping a finding missing kind/id.", file=sys.stderr)
                continue
            yield source, fnd


def key_of(source, fnd):
    return f"{source}:{fnd.get('kind')}:{fnd.get('id')}:{fnd.get('fingerprint', '') or ''}"


def main():
    ap = argparse.ArgumentParser(description="Aggregate radar findings into a review Issue body.")
    ap.add_argument("--finds", required=True, help="directory of *.json findings files")
    ap.add_argument("--seen", default=str(ROOT / "data" / "seen_finds.json"),
                    help="JSON list of already-surfaced finding keys (default data/seen_finds.json)")
    ap.add_argument("--out", required=True, help="path to write the Issue body markdown")
    ap.add_argument("--today", default=date.today().isoformat(), help="run date YYYY-MM-DD")
    args = ap.parse_args()

    finds_dir = Path(args.finds)
    seen_path = Path(args.seen)
    out_path = Path(args.out)
    today = args.today

    seen = load_seen(seen_path)
    seen_set = set(seen)

    # Collect deltas: findings whose key is not already seen, deduped by key.
    delta_keys = []          # new keys, in discovery order
    delta_by_source = {}     # source -> [finding, ...]
    batch_seen = set(seen_set)
    for source, fnd in read_finds(finds_dir):
        k = key_of(source, fnd)
        if k in batch_seen:
            continue
        batch_seen.add(k)
        delta_keys.append(k)
        delta_by_source.setdefault(source, []).append(fnd)

    if not delta_keys:
        # No deltas: write nothing, report false, leave seen untouched.
        emit([("has_findings", "false")])
        return 0

    # Counts for the header/title. Every kind (winners included) is reflected, and
    # zero-count kinds are dropped so a winners-only run never reads "0 new, 0 changed".
    def count(kind):
        return sum(1 for s in delta_by_source for f in delta_by_source[s] if f.get("kind") == kind)
    n_new, m_changed, k_unreach, p_winner = (
        count("new"), count("changed"), count("unreachable"), count("winner"))
    segs = []
    if n_new:
        segs.append(f"{n_new} new")
    if m_changed:
        segs.append(f"{m_changed} changed")
    if k_unreach:
        segs.append(f"{k_unreach} unreachable")
    if p_winner:
        segs.append(f"{p_winner} winner" + ("s" if p_winner != 1 else ""))
    summary = " · ".join(segs) if segs else f"{len(delta_keys)} findings"

    # Compose the Issue body, staying under GitHub's issue-body limit. If the
    # deltas overflow BODY_CAP, include as many as fit and let the rest resurface
    # next run — they are NOT marked seen below, so nothing is ever dropped.
    ordered = [s for s in SOURCE_ORDER if s in delta_by_source]
    ordered += sorted(s for s in delta_by_source if s not in SOURCE_ORDER)
    reserve = len(FOOTER) + 240  # room for the footer + a truncation notice
    lines = [summary, ""]
    included_keys = []
    truncated = False

    def size(ls):
        return sum(len(x) + 1 for x in ls)  # +1 for each newline join

    for source in ordered:
        if truncated:
            break
        header = f"## {SOURCE_LABEL.get(source, source)}"
        section_open = False
        for f in delta_by_source[source]:
            entry = [f"- **{f.get('title') or f.get('id')}** — {f.get('detail') or ''}  ",
                     f"  {f.get('url') or ''}"]
            trial = lines + ([header] if not section_open else []) + entry
            if size(trial) + reserve > BODY_CAP:
                truncated = True
                break
            if not section_open:
                lines.append(header)
                section_open = True
            lines += entry
            included_keys.append(key_of(source, f))
        if section_open:
            lines.append("")

    if truncated:
        remaining = len(delta_keys) - len(included_keys)
        lines.append(f"_Showing {len(included_keys)} of {len(delta_keys)} findings — GitHub caps "
                     f"an issue body at 64 KB. The remaining {remaining} resurface next run._")
        lines.append("")
    lines.append(FOOTER)
    body = "\n".join(lines) + "\n"

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(body, encoding="utf-8")

    # Mark only the findings actually shown as seen; any overflow stays unseen and
    # reappears next run. In the normal (untruncated) case this is every delta.
    # The workflow commits this only after the issue is created.
    seen_path.parent.mkdir(parents=True, exist_ok=True)
    updated = seen + included_keys
    seen_path.write_text(json.dumps(updated, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    title = f"Radar review {today}: {summary}"
    emit([("has_findings", "true"), ("title", title)])
    return 0


if __name__ == "__main__":
    sys.exit(main())
