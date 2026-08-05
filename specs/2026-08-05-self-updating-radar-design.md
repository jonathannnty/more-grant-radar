# Self-updating radar — design spec

_Date: 2026-08-05 · Status: approved, ready to implement_

## Problem

The radar depends on someone manually running the generator + sweep scripts on
Ty's machine to stay current. Two concrete failure modes:

1. **Stale countdowns.** `site/template.html:530` computes `TODAY` from
   `RADAR.today`, a value **baked at build time** by `generate.py --today`. If the
   site is not rebuilt, every "due … · Nd" countdown and the "act now inside
   14/45 days" grouping freeze at the last build date — silently wrong, not
   visibly broken.
2. **Detection depends on human memory.** `scan_grants_gov`, `scan_sam`,
   `winners_feed`, and `nofo_watch` only surface new/changed opportunities when a
   human remembers to run them.

## Goal

A scheduled GitHub Actions workflow that (a) rebuilds and republishes the site
daily so time-sensitive fields stay accurate, and (b) runs the detection sweeps
and surfaces findings as a GitHub Issue for human verification — **without ever
editing the human-verified `data/grants.json`**.

## Non-negotiables (inherited)

- **Verify-first.** No discovered opportunity is ever auto-added to
  `grants.json`. The bot only ever writes *generated* artifacts. Discovered
  items are queued in an Issue for a human to verify against the primary source.
- **No PII in CI.** `partner_match` / `outreach_wave` read the enriched contacts
  export (PII, not in the repo). They are **out of scope** — they stay local.
- **Primary sources only.** Every surfaced finding carries its primary-source URL.

## Architecture — one daily workflow, two phases

Single workflow `.github/workflows/radar.yml`, **one job**, one checkout, two
sequential phases: **Refresh** then **Detect**. Phase 1 commits+pushes its
generated files *before* Phase 2 runs, so the site publishes even if a detection
step later errors (two commits per run, not one).

```
schedule (11:00 UTC daily) / workflow_dispatch
        │
        ▼
┌─ Phase 1: Refresh (always) ─────────────────────────────┐
│ generate.py --today <UTC today>                          │
│   → docs/, data/radar.csv, ics/  regenerated             │
│ commit generated files to main as radar-bot             │
│   → Pages redeploys, Sheet re-imports via IMPORTDATA     │
│ grants.json is READ-ONLY here                            │
└──────────────────────────────────────────────────────────┘
        │
        ▼
┌─ Phase 2: Detect (surface for review) ──────────────────┐
│ scan_grants_gov --json finds/grants_gov.json             │
│ scan_sam        --json finds/sam.json   (SAM_API_KEY)    │
│ nofo_watch --update --json finds/nofo.json               │
│ winners_feed    --json finds/winners.json  (1st of month)│
│        │                                                 │
│        ▼                                                 │
│ radar_review.py  --finds finds/ --seen data/seen_finds.json
│   dedup vs seen → issue_body.md + has_findings output    │
│        │                                                 │
│        ▼ (only if has_findings)                          │
│ gh issue create --title "Radar review …" --body-file …   │
│        │                                                 │
│        ▼                                                 │
│ commit data/seen_finds.json + data/nofo_snapshots.json   │
└──────────────────────────────────────────────────────────┘
```

## Interface contract — the findings JSON (THE thing agents must agree on)

Each detection script gains an **optional** `--json <path>` flag. Existing stdout
behaviour is unchanged (so manual runs still print their markdown report). When
`--json` is given, the script *also* writes this exact structure:

```json
{
  "source": "grants_gov",
  "generated": "2026-08-05",
  "findings": [
    {
      "kind": "new",
      "id": "SM-26-099",
      "title": "Some Opportunity Title",
      "detail": "SAMHSA · open 2026-08-01 · close 2026-10-01 · $2.0M",
      "url": "https://www.grants.gov/search-results-detail/abc123",
      "fingerprint": ""
    }
  ]
}
```

Field rules:
- `source` — one of `grants_gov`, `sam`, `nofo_watch`, `winners`.
- `generated` — the run date (`--today` if the script takes it, else today).
- `kind` — `new` (grants_gov/sam), `winner` (winners), `changed` / `unreachable`
  (nofo_watch).
- `id` — a **stable** unique id within the source: grants.gov opp number, SAM
  notice id, `grant_id` for nofo_watch, awardee id/name for winners.
- `title`, `detail`, `url` — human-facing; `url` MUST be the primary source.
- `fingerprint` — for `changed` items, a short content hash so a *later, different*
  change re-surfaces (dedup key includes it). Empty string for `new`/`winner`.

`findings` is `[]` when the script found nothing. Writing `--json` never fails the
script on a per-source fetch error; unreachable sources are reported as
`kind:"unreachable"` findings (nofo_watch already models this).

## Components

### 1. `--json` emit on the three scanners (+ winners)
- `scan_grants_gov.py`, `scan_sam.py`: add `argparse` `--json PATH`; map their
  existing "fresh/unknown" hit list to `findings` with `kind:"new"`.
- `nofo_watch.py`: already builds a `changes` list of
  `(kind, gid, detail, url)`; map `CHANGED`→`changed` (with `fingerprint` = the
  new content hash), `UNREACHABLE`→`unreachable`, and **omit** `NEW` (a first-seen
  baseline is not a review item). Add `--json PATH`.
- `winners_feed.py`: add `--json PATH` emitting `kind:"winner"` per new awardee.
- Do **not** change any script's default behaviour, exit codes, or stdout.

### 2. `scripts/radar_review.py` (new — the aggregator)
- Args: `--finds <dir>` (reads every `*.json` matching the contract),
  `--seen <path>` (default `data/seen_finds.json`), `--out <issue_body_path>`,
  `--today <date>`.
- Dedup key per finding: `f"{source}:{kind}:{id}:{fingerprint}"`.
- Load seen keys (JSON list; `[]` if file missing). Deltas = findings whose key
  ∉ seen.
- **No deltas** → write nothing; print `has_findings=false` to `$GITHUB_OUTPUT`
  (and stdout); exit 0.
- **Deltas** → compose `issue_body.md`: a short header line
  (`N new · M changed · K unreachable`), then sections grouped by source, each
  finding as `- **{title}** — {detail}  \n  {url}`; a footer restating
  verify-first ("Confirm against the primary source before adding to
  `grants.json`."). Print `has_findings=true` and the issue title
  (`Radar review {today}: {N} new, {M} changed`) to `$GITHUB_OUTPUT`.
- Update the working-copy `seen_finds.json` = seen ∪ delta-keys, in place.
  **The workflow commits it only after the issue is created** (see failure
  handling), so a failed issue-create does not silently swallow finds.
- Stdlib only. UTF-8 stdout guard like the other scripts.

### 3. `data/seen_finds.json` (new, committed)
- Dedup state: a JSON list of already-surfaced finding keys. Non-PII (public
  opportunity numbers/URLs only). Seed as `[]`. **Committed** (unlike
  `data/winners.csv`, which stays git-ignored).

### 4. `.github/workflows/radar.yml` (new)
- `on: schedule: cron "0 11 * * *"` + `workflow_dispatch`.
- `permissions: { contents: write, issues: write }`.
- Steps: checkout → `actions/setup-python` (any 3.x; no deps to install) →
  Phase 1 (generate + **commit+push** generated files) → Phase 2 (scans →
  radar_review → conditional `gh issue create` → **commit+push** seen/baseline).
  Two commits per run: Phase 1's publishes the fresh site regardless of Phase 2.
- Ensure the `radar-review` label exists before creating the issue
  (`gh label create radar-review --color … || true`), since `gh issue create
  --label` fails on a missing label.
- Bot commits: `git config user.name "radar-bot"`, path-scoped
  `git add docs data/radar.csv ics data/nofo_snapshots.json data/seen_finds.json`
  — **never `git add data/grants.json`** (assert this in review).
- Use `gh issue create` (the `gh` CLI is preinstalled on GitHub runners) with
  `GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}`; label `radar-review` (create the label
  if missing, or `--label` with an existing one).
- `winners_feed` step guarded by `if: day-of-month == 01` (compute in a small
  shell step).
- Concurrency guard so overlapping runs don't race on the push
  (`concurrency: { group: radar, cancel-in-progress: false }`).

## Secrets & permissions
- Repo secret `SAM_API_KEY` (for `scan_sam`). If absent, `scan_sam` should emit
  an empty-findings JSON and warn, not fail the workflow.
- `GITHUB_TOKEN` (built-in) for commits + issues; no PAT needed for same-repo.

## Failure handling
- Per-source fetch errors (e.g. the DoD `cdmrp` connection reset already seen) →
  `unreachable` findings, not a workflow failure. Phase 1 already published, so
  the site is fresh regardless.
- Commit-back is path-scoped and idempotent (`git diff --quiet` guard → skip
  commit if nothing changed, avoiding empty commits).
- `seen_finds.json` / baseline commit runs **after** `gh issue create` succeeds,
  so a failed issue-create leaves those finds unseen for the next run.
- A genuine break (`generate.py` throws) fails the run; GitHub emails the owner.
- No `push` trigger → the bot's own commit cannot loop the workflow.

## Out of scope
- `partner_match`, `outreach_wave` (PII, local-only).
- Auto-editing `grants.json` (verify-first — human step, queued via the Issue).
- The Monday team digest / Slack notifications (separate future features).

## Verification plan
- `scan_grants_gov --json` and `nofo_watch --json` run locally; assert the JSON
  validates against the contract and stdout is unchanged.
- `scan_sam --json` verified structurally (no `SAM_API_KEY` in this env → assert
  it emits empty findings + warning, does not crash).
- `radar_review.py` run against the real emitted files **plus** a mock `sam.json`
  and `winners.json`; assert: no-delta path is silent, delta path writes a
  well-formed `issue_body.md` with primary-source URLs, and a second run with the
  same finds produces **zero** deltas (dedup works).
- `radar.yml` parsed as valid YAML; manual review asserts `grants.json` is never
  staged and the issue step is correctly gated on `has_findings`.
- Full end-to-end (issue actually opens) is exercised by a `workflow_dispatch`
  run after merge — noted, not blocked on locally.

## Rollout
1. Land the scripts + workflow on `main`.
2. Add `SAM_API_KEY` repo secret.
3. Trigger once via `workflow_dispatch`; confirm the site rebuilds, a review
   Issue opens (or is correctly silent), and `grants.json` is untouched.
4. Let the daily schedule take over.
