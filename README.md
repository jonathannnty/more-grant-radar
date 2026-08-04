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
scripts/generate.py   grants.json → radar.csv + ics/ + site/index.html + setup.gs payloads
scripts/scan_grants_gov.py   Grants.gov Search2 sweep, diffs against known rows
scripts/scan_sam.py   SAM.gov contract sweep (needs SAM_API_KEY env var)
scripts/winners_feed.py      L4: new SOR/RCORP awardees → data/winners.csv
scripts/partner_match.py     Partner Finder — matches each Sub/Line-item row to candidate
                             partner orgs from the MORE Contact Workflow's enriched export;
                             writes data/partners/ (GIT-IGNORED — contact PII, never on the site)
apps_script/setup.gs  one-shot Google Sheet builder (paste into Apps Script, run setup())
site/template.html    data-driven Cobalt ledger (design per Website Mockup)
site/index.html       generated — deployable to GitHub Pages
ics/                  generated — one .ics per dated row (all-day + −3d alarm)
```

## Daily driver

```
python scripts/generate.py            # rebuild everything from grants.json
python scripts/scan_grants_gov.py    # what's new on Grants.gov (report only)
python scripts/winners_feed.py       # monthly: awardees for the contact pipeline
```

The engine (Claude Code on Ty's machine) edits `data/grants.json` only after
verifying a row against its primary source, then runs `generate.py` and pushes.

## Update rails

- **Rail A (target):** push → `Data_Auto` reads `radar.csv` via `IMPORTDATA`
  (raw.githubusercontent URL, requires public repo) → Sheet + site update from
  one push. Set `RAW_CSV_URL` in `apps_script/setup.gs` and re-run `setup()`.
- **Rail B (works today):** Monday sync pastes `data/radar.csv` into `Data_Auto`
  (File → Import → Upload → Replace data at selected cell, ~60s).
- **Rail C:** Ty-owned Apps Script timer pulling the CSV.

## Non-negotiables

Primary sources only (no grantfinder/grantsights/grantarchive). Verify before a
row enters `grants.json` — `generate.py` refuses rows without a primary URL +
`last_verified` stamp. Expired rows move to `data/archive.csv` with a reason,
never silently deleted. Machines own Data_Auto; humans own Team.
