# Autonomous radar (v4) — design, 2026-10-20

## Why
The v3 design (CI → GitHub review Issue → human verifies → grants.json) stalled silently
after 2026-08-07: 66 review Issues, zero triage, site shrank 22→14 rows, no state/county/
abatement discovery ever ran. Decision (Jonathan, 2026-10-19): the radar must run with
**no human in the loop** and must **never die silently again**.

## Constraints discovered 2026-10-20
- A claude.ai cloud routine cannot do this job: its egress proxy rejects grants.gov and
  state sites, WebFetch fails DNS, and `git push` is 403 (Claude GitHub App not installed).
- GitHub Actions already has open internet + push rights (radar-bot commits daily). So
  everything runs there.

## Architecture
```
daily  (radar.yml, 11:00 UTC)
  Phase 1  generate.py  → docs/ (site), radar.csv, ics/            [always]
  Phase 2  scan_grants_gov → finds/grants_gov.json
           scan_sam (title-gated) → finds/sam.json
           nofo_watch (date-delta only) → finds/nofo.json
           promote_leads.py: finds/* → data/leads.json              [deterministic]
             • grants.gov hits are enriched via fetchOpportunity (deadline, ceiling,
               applicant types, eligibility text, synopsis, forecast dates) → a lead row
             • leads appear on the site immediately in the "Found by the radar" lane
           run_log.py → data/runs.json (every phase writes a stamp)
           commit: docs, data/*.json, radar.csv, ics
weekly (Mondays, same workflow)
  scan_states.py: link-delta watcher over all 50-state + DC agency/settlement pages,
           tracked county pages and the OpioidSettlementTracker grants page → new
           grant-ish links become leads (kind=link)
  ai_pass.py: Claude (Anthropic SDK, web_search + web_fetch server tools) verifies each
           new lead against its primary page, writes verified rows into grants.json
           (with evidence quotes) or rejects with a reason; re-verifies stale rows;
           runs a state/county/abatement discovery sweep for a rotating 10-state slice.
           Gated on secret ANTHROPIC_API_KEY — if absent the step is skipped and the
           site's health panel says so (visible, never silent).
monthly  winners_feed (1st) → data/winners.csv
```

## Guarantees
- grants.json rows still require a primary source URL + last_verified (generate.py refuses
  otherwise). Leads are a separate file and a separate lane, clearly labelled unverified.
- Health is on the page: real run stamps per channel from data/runs.json, a stale banner
  computed client-side (if the page was built > 2 days ago the browser says so, even when
  CI is dead), the AI pass status, and "NEW" badges on rows/leads found in the last 14 days.
- Nothing is ever dropped: leads expire (status=expired) by deadline and are kept 120 days.
- No GitHub Issues are opened any more; the 66 stale ones are closed by the workflow once.

## Files
- data/leads.json — machine-found, unverified (see promote_leads.py docstring for schema)
- data/runs.json — run stamps (phase, ts, status, counts, note), last 200
- data/state_link_baseline.json — scan_states baseline (per page: href→anchor)
- agent/ai_pass_prompt.md — the verification/discovery brief for the AI pass
