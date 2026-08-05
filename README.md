# MORE Grant Radar

Engine + read surfaces for More Therapy's grant-funding radar: every funding
route for MORE (Mindfulness-Oriented Recovery Enhancement) clinician training —
federal NOFOs, state pass-through, opioid-settlement funds, county RFPs,
foundations, workforce money — scored by likelihood × dollars and routed to a
play (Direct / Sub / Line-item / Grant).

**System of record = the Google Sheet.** This repo generates what the Sheet and
the static site consume. Humans own the `Team` tab; the engine owns everything
else. Full context: `MORE Grant Radar — Claude Code Handoff.md` in the OneDrive
deliverables folder.

## Layout

```
data/grants.json      engine-owned source of truth (rows + coverage + state directory)
data/radar.csv        generated — the Data_Auto payload (Sheet imports this)
data/archive.csv      expired/decided rows, with reasons (append-only)
data/seen_finds.json  dedup state (committed) — finding keys already surfaced via a review Issue
scripts/generate.py   grants.json → radar.csv + ics/ + site/index.html + setup.gs payloads
scripts/scan_grants_gov.py   Grants.gov Search2 sweep, diffs against known rows; --json → findings
scripts/scan_sam.py   SAM.gov contract sweep (needs SAM_API_KEY env var); --json → findings
scripts/winners_feed.py      L4: new SOR/RCORP awardees → data/winners.csv; --json → findings
data/profile.json     More Therapy's eligibility profile (registrations, certs, presence)
scripts/accelerators.py      writing accelerators — per-row eligibility label, registration
                             lead-time alert, tailored fit paragraph, deadline checklist
                             (imported by generate.py; the site renders each per opportunity)
scripts/partner_match.py     Partner Finder — matches each Sub/Line-item row to candidate
                             partner orgs from the MORE Contact Workflow's enriched export;
                             writes data/partners/ (GIT-IGNORED — contact PII, never on the site)
scripts/outreach_wave.py     turns a partner shortlist into per-contact draft emails →
                             data/waves/ (GIT-IGNORED — PII; DRAFTS ONLY, never auto-sent)
scripts/nofo_watch.py        change detection — fingerprints each row's NOFO page, diffs vs
                             data/nofo_snapshots.json, flags NEW/CHANGED/UNREACHABLE for review;
                             --json → changed/unreachable findings
scripts/radar_review.py      aggregator — merges the scanners' --json findings, dedups vs
                             data/seen_finds.json, writes the review-Issue body (CI only)
scripts/learning_loop.py     win/loss calibration — aggregates decided Team/archive outcomes
                             by channel/path/eligibility/category → data/learning_report.md
apps_script/setup.gs  one-shot Google Sheet builder (paste into Apps Script, run setup())
site/template.html    data-driven Cobalt ledger (design per Website Mockup)
site/index.html       generated — deployable to GitHub Pages
ics/                  generated — one .ics per dated row (all-day + −3d alarm)
.github/workflows/radar.yml  daily CI — rebuilds+publishes the site, runs the sweeps,
                             opens a review Issue; never edits grants.json
```

## Daily driver

```
python scripts/generate.py            # rebuild everything from grants.json
python scripts/scan_grants_gov.py    # what's new on Grants.gov (report only)
python scripts/winners_feed.py       # monthly: awardees for the contact pipeline
python scripts/nofo_watch.py --update # refresh NOFO change-detection baseline
python scripts/learning_loop.py      # win/loss calibration report
```

## v2: partner outreach + writing accelerators

Two capabilities layer on top of the radar, both reusing the MORE Contact
Workflow's enriched org universe:

1. **Partner Finder → outreach wave.** `partner_match.py` ranks contactable
   partner orgs for every Sub/Line-item opportunity (a for-profit LLC can't win
   these directly, so the play is to be the training line item on someone else's
   application). `outreach_wave.py` then drafts a grant-specific email per
   contact. Both write to git-ignored dirs (`data/partners/`, `data/waves/`) —
   contact PII never touches the public repo or site — and the wave is
   **drafts only**; the compliant send (CAN-SPAM footer, suppression) happens in
   the Contact Workflow's sender, or a human sends. A `partner_status` column
   feeds partner outcomes back for the learning loop.
2. **Writing accelerators** (`accelerators.py`, rendered on the site): each row
   shows whether More Therapy can apply directly vs. sub-only, a registration
   lead-time alert (SAM.gov / eRA Commons take weeks) when a deadline is near, a
   tailored MORE-fit paragraph a writer can drop into the application, and a
   deadline checklist. Evidence figures come from the vetted `MORE_EVIDENCE`
   block — never invented.

The engine (Claude Code on Ty's machine) edits `data/grants.json` only after
verifying a row against its primary source, then runs `generate.py` and pushes.

## Update rails

- **Rail A (target):** push → `Data_Auto` reads `radar.csv` via `IMPORTDATA`
  (raw.githubusercontent URL, requires public repo) → Sheet + site update from
  one push. Set `RAW_CSV_URL` in `apps_script/setup.gs` and re-run `setup()`.
- **Rail B (works today):** Monday sync pastes `data/radar.csv` into `Data_Auto`
  (File → Import → Upload → Replace data at selected cell, ~60s).
- **Rail C:** Ty-owned Apps Script timer pulling the CSV.

## Self-updating radar (CI)

`.github/workflows/radar.yml` runs daily (11:00 UTC) and on demand, in two
sequential phases on one checkout:

1. **Refresh (always).** `generate.py --today <UTC today>` rebuilds the site,
   `radar.csv`, and `ics/`, then commits + pushes them as `radar-bot`. This is
   what keeps countdowns honest: the site reads `RADAR.today`, which is **baked
   at build time**, so without a daily rebuild every "due · Nd" countdown and the
   act-now 14/45-day groupings silently freeze at the last build date.
2. **Detect (surface for review).** The scanners run with `--json`
   (`scan_grants_gov`, `scan_sam`, `nofo_watch --update`, and `winners_feed` on
   the 1st), each emitting findings to `finds/`. `radar_review.py` dedups them
   against `data/seen_finds.json` and, only when there are new deltas, opens a
   GitHub **review Issue** listing each finding with its primary-source URL.
   `seen_finds.json` is committed only after the Issue is created, so a failed
   issue-create leaves those finds unseen for the next run.

Two rails stay intact:

- **`grants.json` is never auto-edited (verify-first).** The bot only writes
  generated artifacts; discovered opportunities are queued in the Issue for a
  human to confirm against the primary source before a row is added.
- **`partner_match` / `outreach_wave` stay local (PII).** They read the enriched
  contacts export and are out of scope for CI — they never run in the workflow.

## Non-negotiables

Primary sources only (no grantfinder/grantsights/grantarchive). Verify before a
row enters `grants.json` — `generate.py` refuses rows without a primary URL +
`last_verified` stamp. Expired rows move to `data/archive.csv` with a reason,
never silently deleted. Machines own Data_Auto; humans own Team.
