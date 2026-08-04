/**
 * MORE Grant Radar — one-time Sheet builder.
 *
 * Install (2 minutes):
 *   1. Create a blank spreadsheet (sheets.new), name it "MORE Grant Radar".
 *   2. Extensions → Apps Script → delete the stub, paste this whole file, save.
 *   3. Run setup() (top toolbar) → authorize when asked → check the sheet.
 *
 * Safe to re-run: engine-owned tabs (Data_Auto, Radar, Playbook, Archive) are
 * rebuilt; the Team tab is human-owned — existing rows are never overwritten,
 * only missing grant_ids are appended.
 *
 * Rail A: set RAW_CSV_URL to the raw.githubusercontent.com URL of data/radar.csv
 * and run switchToRailA() — Data_Auto becomes a live IMPORTDATA feed (Google
 * refreshes roughly hourly) without touching any other tab. Blank = embedded
 * seed snapshot (Rail B).
 *
 * Custom styling: humans may restyle Radar/Playbook freely — but a full setup()
 * re-run rebuilds those tabs and wipes custom formatting. Under Rail A you never
 * need setup() for data refresh, so styling is safe in normal operation.
 *
 * Filter views: enable the Advanced Sheets Service once (editor left sidebar →
 * Services + → "Google Sheets API" → Add, identifier "Sheets"), then run
 * addFilterViews() — creates Jon / Asha / Dr. Garland / Rhea / Unassigned views.
 * NOTE: filter views are INCOMPATIBLE with a Table. If Radar has been converted
 * to a Table (Format → Convert to table), addFilterViews() fails with "can't
 * apply a filter to a range that partially intersects a table" — in that case
 * use the Table's own owner-column dropdown filter instead (shared state).
 *
 * Under Rail A you should NOT re-run setup() (it rebuilds Radar and fights human
 * styling). Refresh happens automatically via IMPORTDATA; run syncTeam() when
 * new grant_ids appear, and switchToRailA() only if the feed URL changes.
 */

var RAW_CSV_URL = 'https://raw.githubusercontent.com/jonathannnty/more-grant-radar/main/data/radar.csv';

// ——— payloads injected by scripts/generate.py — do not hand-edit ———
// <<RADAR_CSV>>
var SEED_RADAR_CSV = "grant_id,name,funder,program,channel,state,path,forprofit_direct,category,accessible_usd,pool_usd,deadline,cycle_watch,likelihood,priority,heart,nofo_url,source_url,portal,accounts_needed,match_required,page_limit,attachments,scoring_map,effort_hrs,kit_type,kit_url,last_verified,next_check,found_date\nyork-county-pa-2027,York County PA opioid settlement \u2014 2027 cycle,York County Board of Commissioners (admin: York County Planning Commission),\"Annual settlement grants, Exhibit E uses; 17 rounds over 18 years\",Settlement-county,PA,Direct/Sub,unclear,SUD,350000,2000000,2026-08-14,,3,16.6,\"York County settlement dollars explicitly fund treatment, recovery, and training under Exhibit E \u2014 a MORE cohort for York County SUD clinicians is a direct remediation use. Open now but GATED: required info sessions already ran.\",https://www.ycpc.org/691/How-to-Apply,https://www.ycpc.org/646/Opioid-Settlement-Funding,ycpc.org FormCenter online application,W-9 signed/dated 2026; info-session attendance,No,Work plan \u22642 pp; support letters \u22643 pp,,,10,line-item-kit,https://docs.google.com/document/d/1nYvlnmWmL0Pmzax3coSLEcJoaJ8hNSCaUN1UWbDcE3Q/edit,2026-08-04,2026-08-06,2026-08-04\nsm-26-014,\"CCBHC Planning, Development & Implementation (SM-26-014)\",SAMHSA,Certified Community Behavioral Health Clinics PDI,Federal-discretionary,US,Line-item,N,MAT-MOUD,9400000,94000000,2026-08-17,,3,20.9,\"94 CCBHCs are writing applications right now \u2014 MORE goes in as their evidence-based line item and strengthens their scoring. Nonprofits and local government only, so this is a pure partner play: the insert kit goes out before the 17th.\",https://www.samhsa.gov/grants/grant-announcements/sm-26-014,https://www.grants.gov/search-results-detail/360977,Grants.gov (partners apply; MORE rides as line item),Partner needs SAM/UEI + Grants.gov + eRA Commons (NOFO: register \u22656 weeks before deadline),No,Project Narrative 15 pp (over = not reviewed); Abstract 1 pp; timeline attachment \u22642 pp,\"16 attachments incl. letters of commitment (#1), licensure + Medicaid proof (#11 \u2014 application not reviewed without it), state BH authority approval letter (#16)\",\"Criterion C names the EBP (5 pts, ~1 page \u2014 the MORE slot) + Criterion B implementation/staffing (35 pts, mandated workforce training on evidence-based non-pharmacological interventions); +5 priority pts for the 100 highest overdose-death counties (NOFO Appendix C) \u2014 that county list is the campaign targeting list\",20,line-item-kit,https://docs.google.com/document/d/1nYvlnmWmL0Pmzax3coSLEcJoaJ8hNSCaUN1UWbDcE3Q/edit,2026-08-04,2026-08-06,2026-08-01\nsamhsa-sm-26-015,CCBHC Improvement & Advancement (SM-26-015),SAMHSA,CCBHC IA for existing clinics; CFDA 93.696; Grants.gov opp 360978,Federal-discretionary,US,Line-item,N,general-BH,11700000,117160647,2026-08-17,,3,21.2,\"117 existing CCBHCs are applying for $1M/yr improvement money right now \u2014 same 8/17 deadline, same insert-kit: MORE named as the Section C EBP and a Section B workforce-training line.\",https://www.samhsa.gov/grants/grant-announcements/sm-26-015,https://www.grants.gov/search-results-detail/360978,Grants.gov / eRA ASSIST (partner applies),Partner needs SAM/UEI + Grants.gov + eRA Commons; More Therapy needs none \u2014 contractor line in partner budget,No,Project Narrative 15 pp,,A need 10-15 pts (+5 priority pts for high opioid-mortality areas); B implementation 35 pts (staffing/training live here); C EBP 5 pts (name MORE); D experience 25; E data 20,10,line-item-kit,https://docs.google.com/document/d/1nYvlnmWmL0Pmzax3coSLEcJoaJ8hNSCaUN1UWbDcE3Q/edit,2026-08-04,2026-08-06,2026-08-04\nsamhsa-sm-26-016,CCBHC State Planning Grants (SM-26-016),SAMHSA,\"Cooperative agreements, Section 223 PAMA; ALN 93.829; Grants.gov opp 360982\",Fed-state-passthrough,US,Line-item,N,general-BH,,12000000,2026-08-17,,2,2.0,\"12 states get $1M each to make clinics certification-ready, and the NOFO explicitly funds training/TA on implementing EBPs with fidelity \u2014 the 12 winners are the next CCBHC training market.\",https://www.samhsa.gov/grants/grant-announcements/sm-26-016,https://www.grants.gov/search-results-detail/360982,Grants.gov (state applies),None for More Therapy \u2014 contracted training/TA vendor inside a state's plan,No,Project Narrative 15 pp,,A need 20; B implementation 35; C experience/staffing 30; D data 15,6,letter-of-support,https://docs.google.com/document/d/1nYvlnmWmL0Pmzax3coSLEcJoaJ8hNSCaUN1UWbDcE3Q/edit,2026-08-04,2026-08-06,2026-08-04\ntn-williamson-cy27,Williamson County TN opioid settlement \u2014 CY27 cycle,Williamson County Opioid Task Force (admin: MTSU OPSR),Annual community abatement grants under TN Opioid Abatement Council strategies,Settlement-county,TN,Direct,Y,SUD,,,2026-08-17,,5,5.0,\"For-profits are explicitly eligible to apply directly, and remediation item FF4 funds 'training providers to offer multi-modal, evidence-informed treatment of pain' \u2014 MORE training for Williamson County clinicians is a verbatim allowable activity. Open now, due Aug 17.\",https://chhs.mtsu.edu/wp-content/uploads/sites/83/2026/07/Williamson-CY27-RFP-APD-3.pdf,https://chhs.mtsu.edu/wcos/,Qualtrics online form (no registrations needed),None,None (in-kind may be listed),No page limit; per-section character limits in the portal,,100 pts: program design 15 (EBPs); budget justification 20 (line items tied to activity codes \u2014 cite FF4/AA9/BB15); need 10; goals 10; capacity 10,15,direct-template,https://docs.google.com/document/d/1nYvlnmWmL0Pmzax3coSLEcJoaJ8hNSCaUN1UWbDcE3Q/edit,2026-08-04,2026-08-06,2026-08-04\nal-admh-settlement-r4,Alabama ADMH Opioid Settlement Round 4 (RFP 2027-04),Alabama Department of Mental Health,Opioid Settlement Grant Program FY2027 (HB487),Settlement-state,AL,Line-item,N,SUD,35000,8930000,2026-08-24,,3,13.6,\"Alabama's $8.9M Round 4 requires applicants to articulate evidence-based practices with training, supervision, and fidelity plans \u2014 MORE training rides as a subcontract line (capped at 10% of award) in ADMH-certified treatment providers' proposals.\",https://mh.alabama.gov/wp-content/uploads/2026/07/RFP-2027-04-Opioid-Settlement-Round-4.pdf,https://mh.alabama.gov/opioid-settlement/,\"PAPER ONLY \u2014 1 original + 2 copies + 1 USB physically received by 2:00 pm CT at ADMH Contracts & Purchasing, Montgomery; email/fax not accepted\",\"Partner needs AL SoS registration, E-Verify, STAARS vendor registration, ADMH certification\",None stated; no supplanting; indirect capped 15%,New proposals: cover 1 + org 2 + program 5 + budget 2 pp,,\"100 pts; program description 30 (EBPs clearly articulated w/ fidelity + training + supervision plans = Section III(e), the MORE slot); understanding 20; experience 15; readiness 15; budget 20\",8,line-item-kit,https://docs.google.com/document/d/1nYvlnmWmL0Pmzax3coSLEcJoaJ8hNSCaUN1UWbDcE3Q/edit,2026-08-04,2026-08-11,2026-08-04\npa-27-100,NIH/NIDA SBIR Phase I (PA-27-100),NIH / NIDA,Parent SBIR (R43/R44) Clinical Trial Optional,Federal-discretionary,US,Direct,Y,SUD,400000,,2026-09-05,,5,28.0,\"The one big pot built for for-profits \u2014 R&D money for the MORE app and training platform. Eric wants the ~$2M path; Phase I is the door, first standard due date Sep 5.\",https://simpler.grants.gov/opportunity/d1ba49e5-3684-4420-849a-ab2330ec493e,https://www.grants.gov/search-results-detail/359671,Grants.gov / NIH ASSIST,SAM/UEI (annual renewal) + SBA Company Registry + eRA Commons + Grants.gov \u2014 6+ weeks of lead; start now,None,,,\"NIH 5-criteria review \u2014 Significance (pain+OUD unmet need), Innovation (~3\u00d7 CBT effect), Approach, Investigators, Environment; NIDA caps Phase I $400K / Phase II $3M\",120,direct-template,https://docs.google.com/document/d/1nYvlnmWmL0Pmzax3coSLEcJoaJ8hNSCaUN1UWbDcE3Q/edit,2026-08-04,2026-08-06,2026-08-01\npcori-substance-use,PCORI \u2014 Addressing Substance Use (Cycle 3 2026),Patient-Centered Outcomes Research Institute,Topical PFA \u2014 comparative clinical-effectiveness research on substance use,Federal-discretionary,US,Direct,Y,SUD,2000000,12000000,2026-09-09,,4,25.2,The cleanest research fit we've found: a head-to-head trial of MORE vs CBT (or MORE + usual care/MOUD) for opioid use disorder is exactly what this funds \u2014 and for-profits can apply directly. Opened today; the LOI gate is Sep 9.,https://www.pcori.org/funding-opportunities/announcement/addressing-substance-use-pcori-funding-announcement-cycle-3-2026,https://www.pcori.org/funding-opportunities,PCORI Online (pcori.org),PCORI Online account; realistically an academic/clinical trial partner,None,,,Merit review; must map to the PFA's substance-use CER priorities with a substance-use primary outcome. Position MORE against CBT/usual care for OUD + co-occurring chronic pain.,200,direct-template,https://docs.google.com/document/d/1nYvlnmWmL0Pmzax3coSLEcJoaJ8hNSCaUN1UWbDcE3Q/edit,2026-08-04,2026-08-11,2026-08-04\nmd-orf-2027-moor,Maryland Opioid Restitution Fund 2027 (MOOR NOFA),Maryland Office of Overdose Response,\"ORF Grant Program, CY2027-28 (settlement Exhibit E uses)\",Settlement-state,MD,Line-item,N,SUD,100000,,2026-09-15,,3,15.0,\"Maryland settlement dollars, $1M ceiling per 2-year project, for evidence-based treatment and staff training \u2014 MORE rides as a named training/subcontract line in a nonprofit partner's application.\",https://stopoverdose.maryland.gov/wp-content/uploads/sites/34/2026/07/MOOR-2027-ORF-NOFA-Revised.pdf,https://stopoverdose.maryland.gov/grants/,Smartsheet application form,\"Partner needs 501(c) letter, MD SDAT good standing, charity registration, 990, W-9; no SAM/Grants.gov\",None stated,,,Staff eligibility screen \u2192 Evaluation Committee ranking (no published points). Must align with a settlement Exhibit E provision + a Project Focus Area; 'evidence-based substance use treatment is allowable' incl. co-occurring.,15,line-item-kit,https://docs.google.com/document/d/1nYvlnmWmL0Pmzax3coSLEcJoaJ8hNSCaUN1UWbDcE3Q/edit,2026-08-04,2026-08-18,2026-08-04\nks-sedgwick-wichita-2026,Sedgwick County / Wichita KS opioid settlement RFPs (4 programs),\"Sedgwick County + City of Wichita, KS\",OUD Treatment/Recovery/Prevention RFPs 26-0080..83 (Kansas Fights Addiction Act local share),Settlement-county,KS,Direct,Y,SUD,200000,2000000,2026-09-15,,5,26.5,\"For-profits check a box on the response form and apply directly \u2014 and RFP 26-0081's Workforce Support goal ($580K, awards to $200K) explicitly funds 'continuing education and skill-building training' for behavioral-health clinicians. A straight MORE training proposal.\",https://www.sedgwickcounty.org/media/73833/26-0081-integrated-care.pdf,https://www.sedgwickcounty.org/finance/purchasing/current-bids-and-proposals/,Email submission to Purchasing@sedgwick.gov (RFP number in subject) \u2014 no portal registration,None,,No hard limits; per-question word guides,,100 pts: understanding/methodology 25; qualifications 20; evidence-based practices 20 (MORE's RCT base); cost 15; performance measures 10; accessibility 10,25,direct-template,https://docs.google.com/document/d/1nYvlnmWmL0Pmzax3coSLEcJoaJ8hNSCaUN1UWbDcE3Q/edit,2026-08-04,2026-08-11,2026-08-04\ntx-oafc-cjs-2026,Texas OAFC \u2014 criminal-justice opioid abatement (targeted cycle),TX Opioid Abatement Fund Council,\"2026 Grant Issuance Plan (amended 3/12/2026) \u2014 Spring 2026 targeted strategy, NOFA pending\",Settlement-state,TX,Direct,Y,MAT-MOUD,2500000,25000000,,2026-09-01,4,25.6,\"Up to $25M for opioid abatement in the criminal-justice system, awards $250K\u2013$2.5M, categories explicitly include Workforce Development and Training \u2014 train jail/reentry clinicians in MORE layered onto MOUD. NOFA overdue; watch closely.\",https://comptroller.texas.gov/programs/opioid-council/docs/grants/Amended-2026-OAFC-grant-issuance-plan.pdf,https://comptroller.texas.gov/programs/opioid-council/grants/grant-opp.php,Texas OGMS (txcomptroller.my.site.com/opioid),TX OGMS account,,,,Plan categories: Treatment & Coordination of Care \u00b7 Recovery Support \u00b7 Workforce Development and Training \u00b7 Prevention/Public Safety,40,direct-template,https://docs.google.com/document/d/1nYvlnmWmL0Pmzax3coSLEcJoaJ8hNSCaUN1UWbDcE3Q/edit,2026-08-04,2026-08-11,2026-08-04\ntx-oafc-core-2026f,Texas OAFC \u2014 Fall 2026 CORE grants,TX Opioid Abatement Fund Council,CORE grant cycle,Settlement-state,TX,Direct/Sub,Y,SUD,1875000,75000000,,2026-09-01,4,25.1,\"Settlement money with provider-friendly eligibility, opening this fall. Watch page and GovDelivery list are live; position before it posts.\",,https://comptroller.texas.gov/programs/opioid-council/grants/grant-opp.php,Texas OGMS,TX OGMS account; TX SmartBuy/CMBL ($70/yr) for vendor path,,,,,40,direct-template,https://docs.google.com/document/d/1nYvlnmWmL0Pmzax3coSLEcJoaJ8hNSCaUN1UWbDcE3Q/edit,2026-08-04,2026-08-11,2026-08-01\nhrsa-rcorp-fy27,HRSA RCORP \u2014 FY27 cycle,HRSA,Rural Communities Opioid Response Program,Federal-discretionary,US,Direct,Y,SUD,750000,64000000,,2027-03-01,4,23.5,\"For-profits are explicitly eligible \u2014 rare for federal treatment money. FY26 closed Jul 8; no FY27 forecast is posted yet, so the radar watches while we prep the rural partner map to apply day one.\",https://simpler.grants.gov/opportunity/e779b908-4f8c-48ce-9485-1345475cdbaf,https://www.hrsa.gov/rural-health/opioid-response,Grants.gov,SAM/UEI + Grants.gov,,,,FY26 shape: Planning HRSA-26-036 $100K \u00d7 40 ($4M) \u00b7 Impact HRSA-26-037 $60M ~80 awards at a $750K per-award CEILING (not minimum) \u00b7 plus a TA NOFO (HRSA-26-038),60,direct-template,https://docs.google.com/document/d/1nYvlnmWmL0Pmzax3coSLEcJoaJ8hNSCaUN1UWbDcE3Q/edit,2026-08-04,2026-08-11,2026-08-01\nheal-translation-rfa-da-27-016,NIH HEAL \u2014 Translating Addiction Research into Practice (RFA-DA-27-016),NIH / NIDA (HEAL Initiative),R61/R33 phased award; ALNs 93.279/93.273/93.866/93.213,Federal-discretionary,US,Direct,Y,SUD,700000,6000000,2026-10-09,,4,23.4,\"NIH money a for-profit can hold directly, whose stated priority is exactly MORE's pitch: getting clinicians trained in and delivering evidence-based addiction treatment, with chronic-pain-comorbid SUD named as a priority. An R61 (train clinicians, pilot fidelity) into R33 (implementation trial) built around MORE dissemination.\",https://files.simpler.grants.gov/opportunities/c33f1e5e-0354-4976-adca-9aa7240778d3/attachments/d20bcf8b-9221-47b2-93d3-2351a3eac1a4/RFA-DA-27-016-Full-Announcement.html,https://www.grants.gov/search-results-detail/362672,NIH ASSIST / Grants.gov Workspace,SAM/UEI + eRA Commons (SO + PI) + Grants.gov + ORCID \u2014 6+ weeks,No,Standard NIH page limits + 2-pp Timeline and Milestone Plan attachment,,\"Standard NIH peer review; R33 transition is administrative against R61 milestones. NON-RESPONSIVE traps: solely testing new interventions, purely descriptive studies \u2014 frame as translation/implementation of the established MORE evidence base.\",100,direct-template,https://docs.google.com/document/d/1nYvlnmWmL0Pmzax3coSLEcJoaJ8hNSCaUN1UWbDcE3Q/edit,2026-08-04,2026-08-11,2026-08-04\nnih-heal-impowr-beacon,\"NIH HEAL IMPOWR BEACON Center (RFA-DA-27-006, forecast)\",NIH / NIDA (HEAL Initiative),BEACON network coordination + capacity-building center (U2C; ALN 93.279),Federal-discretionary,US,Direct/Sub,Y,pain,1750000,1750000,2026-11-02,,3,18.7,\"The single capacity-building hub for scaling evidence-based practices across the chronic pain + OUD consortium \u2014 one award, $1.75M, and clinician training at the EBP/implementation intersection is its core duty.\",,https://www.grants.gov/search-results-detail/360366,Grants.gov,SAM/UEI + eRA Commons + Grants.gov,No,,,,100,,,2026-08-04,2026-08-18,2026-08-04\nallegheny-osf-2026,Allegheny County OSF \u2014 annual RFP,Allegheny County DHS,Opioid Settlement Fund RFP,Settlement-county,PA,Direct/Sub,Y,SUD,500000,,,2026-09-08,3,17.1,\"Annual county settlement RFP \u2014 opens around November, due January. Calendar it; the county pattern of 3\u20136-week windows is the volume play nationwide.\",,https://solicitations.alleghenycounty.us/,Bonfire,Bonfire vendor account (free),,,,,30,direct-template,https://docs.google.com/document/d/1nYvlnmWmL0Pmzax3coSLEcJoaJ8hNSCaUN1UWbDcE3Q/edit,2026-08-04,2026-08-11,2026-08-01\nva-oaa-fy28,Virginia OAA \u2014 locality grants (FY27 window open / FY28),VA Opioid Abatement Authority,City & county grants,Settlement-state,VA,Sub,N,SUD,200000,,2026-10-22,,3,15.9,Every VA city and county has an entitled settlement allocation it can only unlock by submitting an approved abatement project \u2014 get MORE named as the evidence-based training contractor inside locality applications before the Oct 22 new-award cutoff.,https://www.oaa.virginia.gov/media/governorvirginiagov/oaa/documents/Guidance-Individual-Distribution-Gold-Standard.pdf,https://www.oaa.virginia.gov/portal-grants/,OAA Grants Portal (voaagrants.us) \u2014 held by the locality; MORE enters via the locality's contractor budget,Virginia eVA (free),,,,,20,letter-of-support,https://docs.google.com/document/d/1nYvlnmWmL0Pmzax3coSLEcJoaJ8hNSCaUN1UWbDcE3Q/edit,2026-08-04,2026-08-11,2026-08-01\noh-ag-jail-remediation-cy26,Ohio AG Opioid Remediation \u2014 jail addiction programs (CY2026),Office of the Ohio Attorney General,\"Improving Outcomes for Substance-Addicted Inmates (CY2025\u201327, AG settlement funds)\",Settlement-state,OH,Line-item,N,SUD,200000,20000000,2026-12-01,,3,15.9,\"$20M/yr for county jails and CBCFs to stand up addiction programming \u2014 'new contract services related to OUD' explicitly qualifies, so a jail grantee contracts More Therapy to train its treatment staff in MORE. Rolling review through Dec 1.\",https://www.ohioattorneygeneral.gov/getattachment/ed88813d-94c9-4e90-ba0f-7d43614444e2/ed88813d-94c9-4e90-ba0f-7d43614444e2.aspx,https://www.ohioattorneygeneral.gov/getattachment/ed88813d-94c9-4e90-ba0f-7d43614444e2/ed88813d-94c9-4e90-ba0f-7d43614444e2.aspx,\"Email application to JailGrants@OhioAGO.gov \u2014 rolling, quarterly payments\",None for More Therapy; jail needs OH|ID + OhioPays,None stated,,,\"AG review committee; priorities: new programming in shortage areas, multi-county sharing, multi-county jails\",12,line-item-kit,https://docs.google.com/document/d/1nYvlnmWmL0Pmzax3coSLEcJoaJ8hNSCaUN1UWbDcE3Q/edit,2026-08-04,2026-08-18,2026-08-04\noneohio-c3,OneOhio Recovery Foundation \u2014 Cycle 3,OneOhio Recovery Foundation,Regional grant cycle 3,Settlement-state,OH,Direct,Y,SUD,186000,,,2026-11-15,3,15.8,For-profits eligible; Cycle 2 was $45.7M. Roughly annual \u2014 verify More Therapy's 2-year Ohio registration now so eligibility is ready when it opens.,,https://www.oneohiofoundation.com/grants,OneOhio application portal,Ohio SoS registration 2+ yrs,,,,Cycle 2 pattern: RFP Dec 10 \u2192 inquiry Jan 14\u2013Feb 11 \u2192 awards mid-year,40,direct-template,https://docs.google.com/document/d/1nYvlnmWmL0Pmzax3coSLEcJoaJ8hNSCaUN1UWbDcE3Q/edit,2026-08-04,2026-08-11,2026-08-01\nnih-heal-impowr-rm1,\"NIH HEAL IMPOWR \u2014 chronic pain + OUD health systems (RFA-DA-27-001, forecast)\",NIH / NIDA (HEAL Initiative),\"IMPOWR Health Systems, RM1 team award\",Federal-discretionary,US,Direct/Sub,Y,pain,,,2026-11-02,,4,4.0,\"Health-systems implementation of integrative interventions for co-occurring chronic pain + OUD \u2014 MORE's exact dyad and evidence space, and clinician training is a core implementation strategy this NOFO funds. Team with Garland/U. Utah.\",,https://www.grants.gov/search-results-detail/360048,Grants.gov / NIH ASSIST,SAM/UEI + eRA Commons + Grants.gov,No,,,,120,,,2026-08-04,2026-08-18,2026-08-04\noh-sos-passthrough-watch,Ohio SOS 4.0 (SOR pass-through) \u2014 Year 3 RFA watch,\"Ohio Dept. of Behavioral Health (DBH, ex-OhioMHAS)\",\"SAMHSA State Opioid Response pass-through (award H79TI087745, ~$101M/yr)\",Fed-state-passthrough,OH,Line-item,N,SUD,,,,2026-10-01,3,3.0,Ohio's ~$100M/yr SOR pass-through explicitly funds 'expanding evidence-based practices' and names for-profit licensed community BH providers as eligible applicants \u2014 MORE training fits as the EBP line item in provider and ADAMH board applications when Year-3 RFAs post (~fall).,https://dbh.ohio.gov/supporting-providers/apply-for-funding/funding-opportunities/20-rfi-109-sos-4-0-grant,https://dbh.ohio.gov/supporting-providers/apply-for-funding,DBH funding-opportunities carousel,None for More Therapy (partner applies),,,,RFA #109 awards ran $100K\u2013$6M per applicant; short spend windows \u2014 partners need MORE priced and ready before RFAs drop,10,line-item-kit,https://docs.google.com/document/d/1nYvlnmWmL0Pmzax3coSLEcJoaJ8hNSCaUN1UWbDcE3Q/edit,2026-08-04,2026-10-01,2026-08-04\nca-hcai-wet-obj1,CA HCAI BHSA WET Plan \u2014 workforce training vendor watch,California HCAI,\"Behavioral Health Services Act (Prop 1) Workforce Education & Training Plan 2026\u20132030, Objective 1\",Workforce,CA,Sub,unclear,workforce,,,,2026-10-01,3,3.0,\"HCAI will fund development and statewide delivery of training modules cross-training MH and SUD providers in substance-use treatment, MAT, and harm reduction for LCSW/LMFT/LPCC/psychologists \u2014 a near-exact description of MORE clinician training, with CEU alignment planned. No RFP yet; implementation began 7/1/2026.\",https://hcai.ca.gov/document/bhsa-2026-2030-wet-plan/,https://hcai.ca.gov/workforce/financial-assistance/grants/bhp/,Cal eProcure (when solicitations post),Cal eProcure vendor registration (free) when the time comes,,,,Objective 1 sequence: core competencies \u2192 skills-gap analysis \u2192 map existing programs \u2192 fund module development \u2192 delivery to county agencies,10,,,2026-08-04,2026-10-01,2026-08-04\ndod-cdmrp-prmrp,DoD CDMRP \u2014 chronic pain research (PRMRP / CPMRP),US Dept. of Defense \u2014 CDMRP,Peer Reviewed Medical Research Program + Chronic Pain Management Research Program,Federal-discretionary,US,Direct,Y,pain,,,,2027-03-01,3,3.0,\"Rare for-profit-direct DoD money for chronic-pain research \u2014 MORE's pain dyad fits squarely. FY26 entry is closed; FY27 opens ~spring 2027, so we prep and apply on day one.\",,https://cdmrp.health.mil/funding/prmrp,Grants.gov / eBRAP,SAM/UEI + Grants.gov + eBRAP,,,,Peer + programmatic review; frame MORE as a non-pharmacological chronic-pain intervention with military/veteran relevance,100,direct-template,https://docs.google.com/document/d/1nYvlnmWmL0Pmzax3coSLEcJoaJ8hNSCaUN1UWbDcE3Q/edit,2026-08-04,2027-01-15,2026-08-04\n";
// <<END_RADAR_CSV>>
// <<DIRECTORY_CSV>>
var STATE_DIRECTORY_CSV = "state,agency,url,settlement_url,notes\nAlabama,Alabama Department of Mental Health (ADMH) \u2014 Division of Mental Health and Substance Abuse Services (Single State Authority for the Substance Use Prevention & Treatment Block Grant),https://mh.alabama.gov/grants/,https://mh.alabama.gov/faq/opioid-grants/,\"ADMH grants page verified: lists SUD Prevention & Treatment Block Grant, Mental Health Block Grant, PATH, and Substance Use Treatment Initiatives. Opioid settlement path: the AL Legislature appropriated settlement dollars to ADMH to run com\"\nAlaska,Alaska Department of Health \u2014 Division of Behavioral Health (DBH),https://health.alaska.gov/en/services/behavioral-health-grant-funding/,https://health.alaska.gov/en/education/drugs-and-alcohol/opioids-prevention-and-recovery/opioid-settlement/,DBH grant-funding page verified: opportunities are posted on the state Online Public Notices board and via GEMS (gems.dhss.alaska.gov); eligibility per 7 AAC 78.030. Opioid settlement in Alaska is administered by the Dept. of Health (85% st\nArizona,Arizona Health Care Cost Containment System (AHCCCS) \u2013 state Medicaid and behavioral health authority,https://www.azahcccs.gov/Resources/Grants/,https://www.azag.gov/issues/opioids/one-arizona-agreement,\"AHCCCS Current Grants page verified (MHBG, SOR IV, etc.). Settlement funds governed by One Arizona MOU; azag.gov One Arizona Agreement page verified via curl (title 'One Arizona Agreement | Attorney G\"\nArkansas,\"Arkansas Department of Human Services \u2014 Division of Aging, Adult, & Behavioral Health Services (DAABHS) (Single State Authority for the Substance Use Block Grant)\",https://humanservices.arkansas.gov/divisions-shared-services/aging-adult-behavioral-health-services/substance-abuse-prevention/substance-abuse-prevention-grants/,https://www.arorp.org/apply-for-funding/,\"DAABHS grants page (Substance Abuse Prevention Grants) lists SABG, Partnerships for Success, State Opioid Response II, and First Responder CARA; confirmed via ARKDHS domain (WebFetch on the DHS site returned navigation-only rendering, but t\"\nCalifornia,California Department of Health Care Services (DHCS),https://www.dhcs.ca.gov/provgovpart/Pages/Funding_Opportunities_and_Grants_Resources.aspx,https://www.dhcs.ca.gov/services/Pages/Opioid-Settlements-Oversight-Section.aspx,\"Funding page verified (title: 'Funding Opportunities and Grant Resources | DHCS'); also see Program Support & Grants hub https://www.dhcs.ca.gov/providers-partners/program-support-grants/ (fetched, co\"\nColorado,Colorado Behavioral Health Administration (BHA),https://bha.colorado.gov/for-service-providers/funding/funding-opportunities,https://coag.gov/opioids/,BHA funding-opportunities page verified via curl (colorado.gov blocks WebFetch; title 'Funding opportunities | Behavioral Health Administration'). coag.gov/opioids verified \u2014 AG administers ~$912M set\nConnecticut,Connecticut Department of Mental Health and Addiction Services (DMHAS),https://portal.ct.gov/DMHAS/RFPs/Index/RFPs-and-RFQs,https://portal.ct.gov/dmhas/newsworthy/news-items/ct-opioid-settlement-advisory-committee,\"DMHAS RFPs and RFQs page verified as the funding-opportunities/procurement portal (POS RFPs, RFQs, RFIs). CT's Opioid Settlement Advisory Committee (OSAC), established 2022, is co-chaired by the DMHAS Commissioner and a municipal representa\"\nDelaware,Delaware Department of Health and Social Services \u2014 Division of Substance Abuse and Mental Health (DSAMH),https://atrc.dhss.delaware.gov/sor-4-0-funding-opportunities-overview,https://deopioidsettlementfunds.org/grants,\"DSAMH funding-opportunities overview (State Opioid Response 4.0) verified via the Addiction Treatment Resource Center (ATRC), a DSAMH/dhss.delaware.gov property: lists Tier Award Program, grassroots messaging, ECASU mini-grants, ACCESS 988,\"\nDistrict of Columbia,DC Department of Behavioral Health (DBH),https://dbh.dc.gov/page/opportunities,https://dbh.dc.gov/page/office-opioid-abatement,\"DBH is the District's SUD/BH authority; the Opportunities page links to the Request for Applications, Community Mental Health Services Block Grant, and contract opportunities. DBH administers both the MH and SUPTRS block grants. Opioid sett\"\nFlorida,\"Florida Department of Children and Families (DCF), Office of Substance Abuse and Mental Health (SAMH)\",https://www.myflfamilies.com/services/substance-abuse-and-mental-health,https://www.myflfamilies.com/services/samh/florida-opioid-settlement,Both pages fetched and confirmed. SAMH contracts via regional Managing Entities (pass-through path). Settlement page confirms state opioid settlement hub; also relevant: https://opioidimplementation.m\nGeorgia,Georgia Department of Behavioral Health and Developmental Disabilities (DBHDD),https://dbhdd.georgia.gov/,https://www.gaopioidtrust.org/,\"DBHDD homepage verified but has no consolidated grants page (funding posted ad hoc, e.g. AOT grant, SUPTR block grant). Georgia Opioid Crisis Abatement Trust (gaopioidtrust.org) verified \u2014 up to $1.3B\"\nHawaii,\"Hawaii Department of Health, Alcohol and Drug Abuse Division (ADAD)\",https://health.hawaii.gov/substance-abuse/,,ADAD is Hawaii's single state authority for SUD prevention/treatment and administers the SABG and State Opioid Response funds. ADAD lists 'Grants and Contracts' as a core function but has NO dedicated grants/funding-opportunities webpage; p\nIdaho,\"Idaho Department of Health and Welfare, Division of Behavioral Health\",https://healthandwelfare.idaho.gov/providers/behavioral-health-providers/funding-opportunities,https://behavioralhealthcouncil.idaho.gov/idaho-opioid-settlement-fund/,\"DHW Division of Behavioral Health administers the SUPTRS Block Grant and Idaho's State Opioid Response (ISOR). Funding Opportunities page (last updated 2026-07-24) posts announcements such as Recovery Support Services, Warm Handoff, and OBO\"\nIllinois,Illinois Department of Human Services \u2013 Division of Substance Use Prevention and Recovery (SUPR) / Division of Behavioral Health and Recovery,https://www.dhs.state.il.us/page.aspx?item=149872,https://ilopioidsettlements.com/,\"IDHS 'Grant Funded Programs' page verified, lists SUPR funding opportunities by fiscal year (FY2025-FY2027); formal NOFOs go through Illinois GATA/CSFA. ilopioidsettlements.com verified as official ID\"\nIndiana,\"Indiana Family and Social Services Administration (FSSA), Division of Mental Health and Addiction (DMHA)\",https://www.in.gov/fssa/dmha/funding-information/,https://www.in.gov/recovery/settlement,\"DMHA is Indiana's SUD/BH authority, administering the MH and SUD block grants; competitive opportunities (e.g., Opioid Settlement Dollar-for-Dollar Match, SUD Residential Treatment for Women, Recovery Community Center grants) are posted on \"\nIowa,\"Iowa Department of Health and Human Services (Iowa HHS), Behavioral Health\",https://hhs.iowa.gov/health-prevention/behavioral-health/provider-resources/grants,https://www.iowaattorneygeneral.gov/news/opioid-settlement-information,\"Iowa HHS Behavioral Health is the SUD/BH authority; grants page lists SABG/MHBG block grants, IPN (Integrated Provider Network) grant, SOAR, and CCBHC. Competitive funding opportunities (including opioid-settlement rounds under HF 1038, 202\"\nKansas,\"Kansas Department for Aging and Disability Services (KDADS), Behavioral Health Services\",https://www.kdads.ks.gov/provider-home/providers/bhs-funding-opportunities,https://www.ag.ks.gov/reports-resources/affiliated-organizations/kansas-fights-addiction-act-grant-review-board,\"URL UNVERIFIED (bot-blocked) \u2014 confirm by hand. KDADS BHS Funding Opportunities is the official state SUD/BH grants page (surfaced directly from kdads.ks.gov); however the site returns HTTP 403 to both curl and WebFetch (bot-blocking), so t\"\nKentucky,\"Kentucky Cabinet for Health and Family Services \u2014 Department for Behavioral Health, Developmental and Intellectual Disabilities (DBHDID)\",https://www.chfs.ky.gov/agencies/dbhdid/Pages/sud.aspx,https://kyoaac.ky.gov/,\"DBHDID SUD funding page confirmed via WebFetch \u2014 lists active Notices of Funding Opportunity through the Kentucky Overdose Response Effort (KORE), e.g. Contingency Management pilot grants. General CHFS grants hub also exists at https://www.\"\nLouisiana,Louisiana Department of Health (LDH) \u2014 Office of Behavioral Health (OBH),https://www.ldh.la.gov/office-of-behavioral-health,https://laoatf.org/,\"URL UNVERIFIED (bot-blocked) \u2014 confirm by hand. LDH OBH is the official state BH/SUD authority; the OBH page is on the state's own ldh.la.gov domain but returns HTTP 403 to both curl and WebFetch, so content could not be programmatically co\"\nMaine,\"Maine Department of Health and Human Services \u2014 Office of Behavioral Health (OBH, formerly SAMHS)\",https://www.maine.gov/dhhs/obh/about/grants,https://www.maine.gov/ag/about-us/special-projects/maine-recovery-council,\"OBH grants page confirmed via WebFetch \u2014 lists Mental Health Block Grant, Substance Abuse Prevention & Treatment Block Grant, PATH, SOR2, FR-CARA, OD2A. Opioid settlement: Maine Recovery Council under the AG's office; original URL /ag/recov\"\nMaryland,Maryland Department of Health \u2014 Behavioral Health Administration (BHA),https://health.maryland.gov/bha/Pages/index.aspx,https://stopoverdose.maryland.gov/orf/use-of-funds/,\"BHA homepage confirmed via WebFetch as the state BH/SUD authority (oversees inpatient and community behavioral health), but it does not link a standalone grants page; BHA competitive grants and block-grant subawards are announced ad hoc (re\"\nMassachusetts,Massachusetts Department of Public Health \u2013 Bureau of Substance Addiction Services (BSAS),https://www.mass.gov/orgs/bureau-of-substance-addiction-services,https://www.mass.gov/opioid-recovery-and-remediation-fund,\"URL unverified (bot-blocked) \u2014 confirm by hand. mass.gov returns HTTP 403 to all automated fetchers (WebFetch and curl with browser UA), so pages could not be confirmed programmatically; URLs are the standard mass.gov org/topic paths for BSAS and t\"\nMichigan,Michigan Department of Health and Human Services (MDHHS),https://www.michigan.gov/opioids,https://www.michigan.gov/opioids/opioidsettlements,Both URLs verified via curl (titles: 'Substance Use Disorder (SUD) Resources' and 'Opioid Settlements'); michigan.gov blocks WebFetch (403). MDHHS issues Grant Funding Opportunities via EGrAMS (https:\nMinnesota,\"Minnesota Department of Human Services (DHS), Behavioral Health Administration\",https://mn.gov/dhs/partners-and-providers/grants-rfps/open-rfps/,,\"Grants/RFPs page confirmed (header 'Grants and RFPs / mn.gov/dhs | Partners and Providers'); site is bot-protected so full RFP listing renders via JS, but the page resolves to the correct DHS grants section which posts Behavioral Health Div\"\nMississippi,\"Mississippi Department of Mental Health (DMH), Bureau of Behavioral Health\",https://www.dmh.ms.gov/bureau-of-behavioral-health-fy-2027-notice-of-funding-opportunities/,https://attorneygenerallynnfitch.com/opioid-settlement-fund-advisory-council/,\"DMH NOFO page verified: competitive grants across Peer Recovery/Support, Children & Youth, and Alcohol & Drug Addiction Treatment Services divisions; only DMH Certified Providers eligible. Opioid Settlement Fund Advisory Council (AG Lynn Fi\"\nMissouri,\"Missouri Department of Mental Health (DMH), Division of Behavioral Health\",https://dmh.mo.gov/behavioral-health/block-grant,https://moopioidsettlements.dmh.mo.gov/,\"DMH/DBH block grant page verified: combined MHBG + SUPTRS block grant administered annually; plans posted for comment (DBHResearch@dmh.mo.gov). Missouri opioid settlement reporting site verified, run by DMH (lead agency); state share deposi\"\nMontana,\"Montana Department of Public Health and Human Services (DPHHS), Behavioral Health and Developmental Disabilities Division (BHDD)\",https://dphhs.mt.gov/BHDD/Prevention/SubstanceUseBlockGrant,https://montanaopioid.org/grant-portal/,\"DPHHS BHDD Substance Use Block Grant (SUBG) page verified. Opioid abatement is handled largely outside DPHHS by the Montana Opioid Abatement Trust (MOAT, ~70% share), whose Grant Portal is verified and accepts applications routed through 14\"\nNebraska,\"Nebraska Department of Health and Human Services (DHHS), Division of Behavioral Health\",https://dhhs.ne.gov/Pages/Grants-and-Contract-Opportunities.aspx,https://ago.nebraska.gov/nebraska-opioid-settlement-remediation-advisory-committee,DHHS Office of Procurement and Grants opportunities hub verified (informational; specific listings on /Pages/Grant-Opportunities.aspx and /Pages/Contract-Opportunities.aspx). DHHS Division of Behavioral Health administers SUPTRS/MHBG block \nNevada,\"Nevada Department of Health and Human Services (DHHS), Division of Public and Behavioral Health (DPBH), Bureau of Behavioral Health, Wellness and Prevention (BBHWP) \u2014 the state's Substance Abuse Prevention and Treatment Agency (SAPTA / Single State Authority)\",https://dpbh.nv.gov/Programs/BBHWP/SOR/SOR4RFA/,https://www.dhs.nv.gov/Programs/frn/,\"Grants URL verified (HTTP 200; DPBH State Opioid Response SOR 4 RFA funding-opportunity page, project period 1/1/2025\u20139/29/2027). BBHWP also runs the SUPTRS Block Grant RFA, but the specific SUPTRS_RFA path 404s to automated fetch, so the c\"\nNew Hampshire,\"New Hampshire Department of Health and Human Services (DHHS), Bureau of Drug and Alcohol Services (BDAS) \u2014 the state's Single State Authority for substance use; administers the SAMHSA SUPTRS/SABG block grant\",https://www.dhhs.nh.gov/programs-services/health-care/substance-misuse/substance-abuse-prevention-and-treatment-block-grant,https://www.dhhs.nh.gov/about-dhhs/advisory-organizations/nh-opioid-abatement-trust-fund-advisory-commission,\"URL UNVERIFIED (bot-blocked) \u2014 confirm by hand. Both URLs are legitimate official dhhs.nh.gov pages surfaced by search, but the NH DHHS site returns HTTP 403 to automated fetch/curl (bot-blocking), so page content could not be directly conf\"\nNew Jersey,NJ Department of Human Services \u2013 Division of Mental Health and Addiction Services (DMHAS),https://nj.gov/humanservices/dmhas/,https://www.nj.gov/opioidfunds/,DMHAS homepage verified; it has a 'Funding Opportunities' section under Notices and links directly to the verified nj.gov/opioidfunds opioid settlement fund site (>$1B through 2038).\nNew Mexico,\"New Mexico Health Care Authority (HCA), Behavioral Health Services Division (BHSD) \u2014 formerly under the Human Services Department; the state SUD/BH authority overseeing non-Medicaid behavioral health and SB3 reform funding\",https://www.hca.nm.gov/lookingforinformation/open-rfps/,,Open RFPs page verified (HTTP 200); lists behavioral-health RFP/RFI opportunities including BHSD SBIRT training (up to $4M for SFY27) and ASO administration for SB3 Behavioral Health Reform & Investment Act funds. BHSD awards are typically \nNew York,NYS Office of Addiction Services and Supports (OASAS),https://oasas.ny.gov/funding-opportunities,https://oasas.ny.gov/opioid-settlement-fund,\"Funding page fetched and confirmed: RFP/RFA table with due dates. Settlement-fund URL returned 403/Cloudflare challenge on fetch ('Just a moment...') so settlement page content unconfirmed, but fundin\"\nNorth Carolina,\"NC DHHS \u2013 Division of Mental Health, Developmental Disabilities and Substance Use Services (DMH/DD/SUS)\",https://www.ncdhhs.gov/divisions/mental-health-developmental-disabilities-and-substance-use-services/grants/mental-health-developmental-disabilities-and-substance-use-services-grant-opportunities,https://ncopioidsettlement.org/,\"Grant opportunities page verified (currently no open RFAs; email list rfa.responses@dhhs.nc.gov). ncopioidsettlement.org (CORE-NC) verified as official settlement hub run by NC DOJ, NCACC, UNC IPRC, a\"\nNorth Dakota,\"North Dakota Department of Health and Human Services (HHS), Behavioral Health Division \u2014 the state SUD/BH authority administering the SAMHSA SUPTRS Block Grant, State Opioid Response, and Opioid Settlement Fund grants\",https://www.hhs.nd.gov/behavioral-health/funding-opportunities,,\"Funding-opportunities page verified (HTTP 200); lists provider funding pathways (1915(i) SPA, Community Connect, Free Through Recovery, Recovery Housing, SUD Voucher). The ND Opioid Settlement Fund Grant (NDCC ch. 50-36, Opioid Settlement A\"\nOhio,Ohio Department of Behavioral Health (formerly OhioMHAS; mha.ohio.gov now 301-redirects to dbh.ohio.gov),https://dbh.ohio.gov/supporting-providers/apply-for-funding,https://www.oneohiofoundation.com/,\"Agency renamed: mha.ohio.gov redirects to dbh.ohio.gov. Funding page verified via curl (title 'Apply for Funding'; WebFetch got 404 due to bot-blocking, curl with browser UA got 200). OneOhio Recovery\"\nOklahoma,Oklahoma Department of Mental Health and Substance Abuse Services (ODMHSAS) \u2014 the state SUD/BH authority; issues block-grant and RFP-based contracts,https://oklahoma.gov/odmhsas/about/public-information/grant-and-solicitations.html,https://oklahoma.gov/oag/resources/grants/opioid-abatement-grant.html,Both URLs verified (HTTP 200). ODMHSAS Grants & Solicitations page lists block-grant applications (FFY26-27) and directs contract opportunities through the OMES Central Purchasing RFP process. Opioid settlement is administered separately by\nOregon,\"Oregon Health Authority (OHA), Behavioral Health Division\",https://www.oregon.gov/oha/hsd/amh/pages/bhi-programs.aspx,,OHA Behavioral Health Division administers SUD/MH block grants and behavioral health investment grants. Verified page = Behavioral Health Investments Programs. Oregon's opioid settlement funds are directed by the Opioid Settlement Preventio\nPennsylvania,Pennsylvania Department of Drug and Alcohol Programs (DDAP),https://www.pa.gov/agencies/ddap/for-professionals/funding-opportunities,https://www.paopioidtrust.org/,\"Funding page fetched and confirmed: DDAP 'Grant Initiative Funding Opportunities' (GIFAs). Settlement: Pennsylvania Opioid Misuse and Addiction Abatement Trust, verified via curl (title 'PAOpioidTrust\"\nRhode Island,\"RI Department of Behavioral Healthcare, Developmental Disabilities and Hospitals (BHDDH)\",https://bhddh.ri.gov/mental-health/bhddh-grant-information,https://eohhs.ri.gov/Opioid-Settlement-Advisory-Committee,\"BHDDH is the state BH/SUD authority (block grants MHBG/SUPTRS, PATH, Synar). Opioid settlement dollars are administered separately by the RI Executive Office of Health and Human Services (EOHHS) via the Opioid Settlement Advisory Committee \"\nSouth Carolina,\"SC Office of Substance Use Services (OSUS) \u2014 formerly DAODAS, now under the Dept. of Behavioral Health and Developmental Disabilities (BHDD)\",https://www.daodas.sc.gov/about/grants,https://scorf.sc.gov,DAODAS was restructured into the Office of Substance Use Services (OSUS) under the new SC Dept. of Behavioral Health and Developmental Disabilities; the daodas.sc.gov domain is still live and hosts the grants page (verified). Opioid settlem\nSouth Dakota,\"SD Department of Social Services (DSS), Division of Behavioral Health\",https://dss.sd.gov/behavioralhealth/grantinfo.aspx,,\"DSS Division of Behavioral Health is the state BH/SUD authority (SAPT/MH block grants, CCBHC, PATH, 988). Verified grant-info page also hosts the Opioid Settlement Abatement Funds community grant program (Resource/Organizational/Transformat\"\nTennessee,Tennessee Department of Mental Health and Substance Abuse Services (TDMHSAS),https://www.tn.gov/behavioral-health/for-providers/grants-management.html,https://www.tn.gov/oac.html,\"TDMHSAS is the state BH/SUD authority; verified page is its Grants Management hub for providers (grantee manual, compliance) \u2014 note it is a resource/guidance hub rather than a live NOFO list. Opioid settlement dollars are administered by th\"\nTexas,Texas Health and Human Services Commission (HHSC),https://www.hhs.texas.gov/business/grants,https://comptroller.texas.gov/programs/opioid-council/,\"URL unverified (bot-blocked) \u2014 confirm by hand. HHSC grants URL returned 403 Access Denied to both WebFetch and curl (Akamai bot-blocking) \u2014 could not confirm content, so verified=false for the HHSC page. Settlement page IS verified: Texas Opioid A\"\nUtah,\"Utah Department of Health and Human Services, Office of Substance Use and Mental Health (SUMH)\",https://dhhs.utah.gov/block-grants/,https://sumh.utah.gov/data-reports/opioidlitigation/,SUMH is Utah's state behavioral-health/SUD authority; it administers the Combined MHBG/SUPTRS block grants (public comment Aug 1-30; applications available after Oct 31). Utah has no separate opioid-abatement board site: ~$495M over 18 yrs \nVermont,\"Vermont Department of Health, Division of Substance Use Programs (DSU)\",https://www.healthvermont.gov/alcohol-drugs/grantees-contractors,https://www.healthvermont.gov/alcohol-drugs/public-meetings-comments/opioid-settlement-advisory-committee,\"In Vermont the SUD grant authority is the Dept of Health's Division of Substance Use Programs (DSU), not the separate Dept of Mental Health. The grantees-contractors page hosts active RFPs/RFIs/RFAs (several funded by opioid settlement doll\"\nVirginia,Virginia Department of Behavioral Health and Developmental Services (DBHDS),https://dbhds.virginia.gov/,https://www.oaa.virginia.gov/portal-grants/,DBHDS main site verified via curl (title confirms DBHDS); no single consolidated DBHDS grants page found (/about-dbhds/grants/ is 404). Settlement: Virginia Opioid Abatement Authority official .gov si\nWashington,Washington State Health Care Authority (HCA) \u2013 Division of Behavioral Health and Recovery,https://www.hca.wa.gov/about-hca/programs-and-initiatives/behavioral-health-and-recovery,https://waportal.org/health-initiatives/pregnant-parenting-children-families-and-substance-use-workgroup/opioid-settlement-funds,HCA main behavioral-health page verified (no consolidated grants page; grants like BHI and SAMHSA block grants are posted as subpages). The former waportal.org/partners/washington-state-opioid-settlem\nWest Virginia,\"West Virginia Department of Human Services, Bureau for Behavioral Health (BBH)\",https://bbh.wv.gov/bbh-funding,https://wvfirst.org/grants/,\"BBH is the state SUD/BH authority; bbh-funding page has Current Funding Announcements, Applying for Funding, and Archived Announcements. Opioid settlement funds are largely distributed by the West Virginia First Foundation (WVFF), a separat\"\nWisconsin,\"Wisconsin Department of Health Services (DHS) \u2014 Division of Care and Treatment Services, Bureau of Prevention Treatment and Recovery\",https://www.dhs.wisconsin.gov/business/solicitations-list.htm,https://www.dhs.wisconsin.gov/opioids/index.htm,DHS is the state BH/SUD authority; the 'Current Grant Funding Opportunities' (solicitations-list) page lists active solicitations by due date (also posted to Wisconsin Public Notices/VendorNet). Wisconsin has no independent settlement board\nWyoming,\"Wyoming Department of Health, Behavioral Health Division (Mental Health & Substance Use Treatment Services)\",https://health.wyo.gov/behavioralhealth/mhsa/public-notices/,https://health.wyo.gov/admin/opioid-settlement-funds/,\"The Behavioral Health Division's Grants & Programs Unit administers federal SUD/MH funding; the Public Notices page carries current RFAs (e.g., 2027 Combined MHBG/SUPTRS block grant, community treatment/recovery-housing solicitations). No s\"\n";
// <<END_DIRECTORY_CSV>>

var DATA_COLS = 30; // Data_Auto schema width (A..AD)
var STATUS_LIST = ['New', 'Reviewing', 'Pursuing-Direct', 'Pursuing-Sub', 'Submitted', 'Won', 'Lost', 'Passed'];
var OWNER_LIST = ['Jon', 'Asha', 'Dr. Garland', 'Rhea'];  // people who work the grants

/** Live status/owner feed for the website. Deploy this project as a Web App
 * (Deploy -> New deployment -> Web app -> Execute as: Me -> Who has access:
 * Anyone) and put the /exec URL in the site's TEAM_FEED_URL. Returns ONLY
 * grant_id -> {status, owner, next_action} (never the private notes/why_passed),
 * so the public site can reflect Team edits within seconds, no rebuild. */
function doGet(e) {
  var sh = SpreadsheetApp.getActiveSpreadsheet().getSheetByName('Team');
  var vals = sh.getDataRange().getValues();
  var out = {};
  for (var i = 1; i < vals.length; i++) {
    var id = String(vals[i][0]).trim();
    if (!id) continue;
    out[id] = { status: vals[i][1], owner: vals[i][2], next_action: vals[i][4] };
  }
  return ContentService.createTextOutput(JSON.stringify(out))
    .setMimeType(ContentService.MimeType.JSON);
}

/** Owner-column dropdown on the Team tab. Warning (not reject) so a part-time
 * writer's name can still be typed. Safe to run standalone anytime. */
function addOwnerDropdown() {
  var sh = SpreadsheetApp.getActiveSpreadsheet().getSheetByName('Team');
  var rule = SpreadsheetApp.newDataValidation().requireValueInList(OWNER_LIST, true).setAllowInvalid(true).build();
  sh.getRange(2, 3, 999, 1).setDataValidation(rule);
  Logger.log('Owner dropdown applied to Team!C2:C1000 — ' + OWNER_LIST.join(', '));
}

function setup() {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  buildDataAuto(ss);
  buildTeam(ss);
  buildRadar(ss);
  buildPlaybook(ss);
  buildArchive(ss);
  syncTeam(ss);
  orderTabs(ss);
  Logger.log('Done. Manual finishers (Apps Script cannot create these):');
  Logger.log('1. Per-owner filter views: open Radar → Data → Filter views → Create new filter view.');
  Logger.log('   Make one per owner (filter the owner column) + one "Unassigned" (owner is blank). ~30s each.');
  Logger.log('2. Share: Share button → Jon (jon@moretherapy.com), Asha, writers — Editor.');
  Logger.log('3. Weekly: re-run syncTeam() after new rows land (or just add missing ids by hand).');
}

function sheetReset(ss, name) {
  var sh = ss.getSheetByName(name);
  if (sh) { sh.clear(); sh.clearConditionalFormatRules(); }
  else { sh = ss.insertSheet(name); }
  return sh;
}

// ————— Data_Auto: engine-owned, machines write, humans read —————
function buildDataAuto(ss) {
  var sh = sheetReset(ss, 'Data_Auto');
  if (RAW_CSV_URL) {
    sh.getRange('A1').setFormula('=IMPORTDATA("' + RAW_CSV_URL + '")');
  } else {
    var rows = Utilities.parseCsv(SEED_RADAR_CSV);
    if (rows.length) sh.getRange(1, 1, rows.length, rows[0].length).setValues(rows);
  }
  sh.setFrozenRows(1);
  sh.getRange(1, 1, 1, DATA_COLS).setFontWeight('bold').setFontFamily('Roboto Mono').setFontSize(9);
  sh.autoResizeColumns(1, 9);
  var prot = sh.protect().setDescription('Engine-owned — edits are overwritten on every refresh. Human edits go in Team.');
  prot.setWarningOnly(true);
}

// ————— Team: human-owned, never overwritten —————
function buildTeam(ss) {
  var sh = ss.getSheetByName('Team');
  if (!sh) {
    sh = ss.insertSheet('Team');
    sh.getRange(1, 1, 1, 6).setValues([['grant_id', 'status', 'owner', 'notes', 'next_action', 'why_passed']]);
  }
  sh.setFrozenRows(1);
  sh.getRange(1, 1, 1, 6).setFontWeight('bold');
  var rule = SpreadsheetApp.newDataValidation().requireValueInList(STATUS_LIST, true).setAllowInvalid(false).build();
  sh.getRange(2, 2, 999, 1).setDataValidation(rule);
  var ownerRule = SpreadsheetApp.newDataValidation().requireValueInList(OWNER_LIST, true).setAllowInvalid(true).build();
  sh.getRange(2, 3, 999, 1).setDataValidation(ownerRule);
  sh.setColumnWidth(4, 320);
  sh.setColumnWidth(5, 260);
  sh.setColumnWidth(6, 260);
}

/** Append a Team row for any Data_Auto grant_id not yet present (never overwrites). */
function syncTeam(ss) {
  ss = ss || SpreadsheetApp.getActiveSpreadsheet();
  SpreadsheetApp.flush();
  var da = ss.getSheetByName('Data_Auto');
  var team = ss.getSheetByName('Team');
  var last = da.getLastRow();
  if (last < 2) { Logger.log('Data_Auto empty (IMPORTDATA still loading?) — re-run syncTeam() in a minute.'); return; }
  var ids = da.getRange(2, 1, last - 1, 1).getValues().map(function (r) { return String(r[0]).trim(); }).filter(String);
  var have = {};
  if (team.getLastRow() > 1) {
    team.getRange(2, 1, team.getLastRow() - 1, 1).getValues().forEach(function (r) { have[String(r[0]).trim()] = true; });
  }
  var add = ids.filter(function (id) { return !have[id]; }).map(function (id) { return [id, 'New', '', '', '', '']; });
  if (add.length) team.getRange(team.getLastRow() + 1, 1, add.length, 6).setValues(add);
  Logger.log('Team sync: ' + add.length + ' new id(s) appended.');
}

// ————— Radar: the human view — joins Data_Auto + Team, sorted by the engine —————
function buildRadar(ss) {
  var sh = sheetReset(ss, 'Radar');
  var headers = ['grant_id', 'name', 'funder', 'channel', 'state', 'path', 'deadline', 'runway',
                 'likelihood', 'priority', 'accessible_usd', 'status', 'owner', 'next_action',
                 'heart', 'nofo', 'last_verified'];

  // Roll-up header (row 1)
  sh.getRange('A1').setValue('MORE GRANT RADAR').setFontWeight('bold');
  sh.getRange('C1').setFormula('="rows: "&COUNTA(A4:A)');
  sh.getRange('D1').setFormula('="🔴 ≤14d: "&COUNTIFS(H4:H,"<=14",H4:H,">=0")');
  sh.getRange('E1').setFormula('="🟡 ≤45d: "&COUNTIFS(H4:H,"<=45",H4:H,">=0")');
  sh.getRange('F1').setFormula('="pursuing: "&(COUNTIF(L4:L,"Pursuing*")+COUNTIF(L4:L,"Submitted"))');
  sh.getRange('G1').setFormula('="Σ accessible: $"&TEXT(SUM(K4:K),"#,##0")');
  sh.getRange('I1').setFormula('="Σ pursuing: $"&TEXT(SUMIF(L4:L,"Pursuing*",K4:K)+SUMIF(L4:L,"Submitted",K4:K),"#,##0")');
  sh.getRange(1, 1, 1, 17).setFontFamily('Roboto Mono').setFontSize(9);

  sh.getRange(3, 1, 1, headers.length).setValues([headers]).setFontWeight('bold')
    .setBackground('#eef1f7');
  sh.setFrozenRows(3);

  // Data_Auto columns: A id, B name, C funder, E channel, F state, G path, L deadline,
  // N likelihood, O priority, K accessible, P heart, Q nofo_url, AB last_verified.
  var f = {
    A: '=ARRAYFORMULA(IF(Data_Auto!A2:A="",,Data_Auto!A2:A))',
    B: '=ARRAYFORMULA(IF(Data_Auto!A2:A="",,Data_Auto!B2:B))',
    C: '=ARRAYFORMULA(IF(Data_Auto!A2:A="",,Data_Auto!C2:C))',
    D: '=ARRAYFORMULA(IF(Data_Auto!A2:A="",,Data_Auto!E2:E))',
    E: '=ARRAYFORMULA(IF(Data_Auto!A2:A="",,Data_Auto!F2:F))',
    F: '=ARRAYFORMULA(IF(Data_Auto!A2:A="",,Data_Auto!G2:G))',
    G: '=ARRAYFORMULA(IF(Data_Auto!A2:A="",,Data_Auto!L2:L))',
    H: '=ARRAYFORMULA(IF(Data_Auto!L2:L="",,IFERROR(DATEVALUE(Data_Auto!L2:L),Data_Auto!L2:L)-TODAY()))',
    I: '=ARRAYFORMULA(IF(Data_Auto!A2:A="",,Data_Auto!N2:N))',
    J: '=ARRAYFORMULA(IF(Data_Auto!A2:A="",,Data_Auto!O2:O))',
    K: '=ARRAYFORMULA(IF(Data_Auto!A2:A="",,Data_Auto!J2:J))',
    L: '=ARRAYFORMULA(IF(A4:A="",,IFERROR(VLOOKUP(A4:A,Team!$A:$F,2,FALSE),"New")))',
    M: '=ARRAYFORMULA(IF(A4:A="",,IFERROR(VLOOKUP(A4:A,Team!$A:$F,3,FALSE),"")))',
    N: '=ARRAYFORMULA(IF(A4:A="",,IFERROR(VLOOKUP(A4:A,Team!$A:$F,5,FALSE),"")))',
    O: '=ARRAYFORMULA(IF(Data_Auto!A2:A="",,Data_Auto!P2:P))',
    P: '=ARRAYFORMULA(IF(Data_Auto!Q2:Q="",,HYPERLINK(Data_Auto!Q2:Q,"NOFO →")))',
    Q: '=ARRAYFORMULA(IF(Data_Auto!A2:A="",,Data_Auto!AB2:AB))'
  };
  for (var col in f) sh.getRange(col + '4').setFormula(f[col]);

  // Cosmetic layer — skipped gracefully if the human converted Radar to a Table
  // (typed columns reject setNumberFormat, and a Table brings its own formatting +
  // per-column filtering). The data formulas above are what matter; formatting is
  // best-effort so setup() never aborts on a styled sheet.
  try {
    sh.getRange('K4:K1000').setNumberFormat('$#,##0');
    sh.getRange('H4:H1000').setNumberFormat('0');
    sh.getRange('G4:G1000').setNumberFormat('yyyy-mm-dd');
    sh.setColumnWidth(2, 300);
    sh.setColumnWidth(15, 420);
    sh.setColumnWidth(14, 220);

    var full = sh.getRange('A4:Q1000');
    var rules = [
      SpreadsheetApp.newConditionalFormatRule()
        .whenFormulaSatisfied('=AND($H4<>"",$H4>=0,$H4<=14)')
        .setBackground('#fbe7e5').setRanges([full]).build(),
      SpreadsheetApp.newConditionalFormatRule()
        .whenFormulaSatisfied('=AND($H4<>"",$H4>14,$H4<=45)')
        .setBackground('#fdf3d8').setRanges([full]).build(),
      SpreadsheetApp.newConditionalFormatRule()
        .setGradientMinpoint('#ffffff').setGradientMaxpoint('#c7d2f2')
        .setRanges([sh.getRange('J4:J1000')]).build()
    ];
    sh.setConditionalFormatRules(rules);
  } catch (e) {
    Logger.log('buildRadar: skipped default formatting (Radar is likely a Table) — ' + e.message);
  }

  try {
    var prot = sh.protect().setDescription('View tab — formulas only. Statuses/owners live in Team.');
    prot.setWarningOnly(true);
  } catch (e) { /* protection optional */ }
}

// ————— Playbook: source map, rubric, agency directory, how-to —————
function buildPlaybook(ss) {
  var sh = sheetReset(ss, 'Playbook');
  var rows = [];
  function section(title) { rows.push([]); rows.push(['— ' + title + ' —', '', '', '']); }

  rows.push(['MORE GRANT RADAR — PLAYBOOK', '', '', '']);

  section('HOW TO USE (60 seconds)');
  [['1', 'Open the Radar tab. Red rows are due inside 14 days; amber inside 45.', '', ''],
   ['2', 'Claim a row: put your name in Team → owner for that grant_id.', '', ''],
   ['3', 'Work it: keep status current in Team (dropdown). Notes + next_action live there too.', '', ''],
   ['4', 'Passing on one? Set status Passed and say why in why_passed — the decision log.', '', ''],
   ['5', 'Found money we missed? Email radar@moretherapy.com — it gets triaged Monday.', '', '']
  ].forEach(function (r) { rows.push(r); });

  section('PATHS — how MORE gets the money (the path column)');
  [['Direct', 'More Therapy is the applicant — we apply for and hold the grant ourselves.', 'for-profit-eligible programs (SBIR, RCORP, some settlement RFPs)', ''],
   ['Sub', 'A partner applies; More Therapy is a named subcontractor in their application.', 'settlement grants where only govs/nonprofits apply', ''],
   ['Line-item', "Our training is written in as a budget line inside a partner's application.", 'CCBHC applicants, state plans', ''],
   ['Direct/Sub', 'Could go either way — depends on whether we apply ourselves or team with a partner.', '', ''],
   ['Grant', 'Generic/straight grant (rarely used — treat like Direct).', '', '']
  ].forEach(function (r) { rows.push(r); });

  section('SCORING RUBRIC — likelihood 1-5, priority = likelihood × log10(accessible $)');
  [['5', 'For-profit-direct eligible + addiction/MAT core + open now', 'e.g. NIDA SBIR', ''],
   ['4', 'Direct-eligible, strong fit, competitive or opening soon', 'e.g. RCORP, TX CORE', ''],
   ['3', 'Line-item/sub with partner identified or reachable', 'e.g. SM-26-014 via CCBHC associations', ''],
   ['2', 'Sub path, no partner yet', 'e.g. VA OAA', ''],
   ['1', 'Long shot / eligibility unclear', '', '']
  ].forEach(function (r) { rows.push(r); });

  section('SOURCE MAP — what the engine watches');
  rows.push(['channel', 'source', 'cadence', 'url']);
  [['Federal', 'simpler.grants.gov + Search2 API', 'daily', 'https://simpler.grants.gov'],
   ['Federal', 'SAMHSA dashboard + forecasts', 'daily', 'https://www.samhsa.gov/grants/grants-dashboard'],
   ['Federal', 'HHS newsroom', 'daily', 'https://www.hhs.gov/press-room'],
   ['Settlement-national', 'OpioidSettlementTracker', 'weekly', 'https://www.opioidsettlementtracker.com/grants'],
   ['Settlement-OH', 'OneOhio Recovery Foundation', 'weekly', 'https://www.oneohiofoundation.com/grants'],
   ['Settlement-TX', 'TX Opioid Abatement Fund Council', 'weekly', 'https://comptroller.texas.gov/programs/opioid-council/grants/grant-opp.php'],
   ['Settlement-VA', 'VA Opioid Abatement Authority', 'weekly', 'https://www.oaa.virginia.gov/portal-grants/'],
   ['State-NY', 'NY OASAS procurement', 'weekly', 'https://oasas.ny.gov/procurement'],
   ['Settlement-CA', 'CA Opioid Response', 'weekly', 'https://californiaopioidresponse.org/opportunities/current-funding-opportunities/'],
   ['Workforce-CA', 'HCAI BH workforce grants', 'weekly', 'https://hcai.ca.gov/workforce/financial-assistance/grants/bhp/'],
   ['Foundation', 'FORE · Arnold Ventures · RWJF · Kresge · Bloomberg · Hilton · Elevance', 'weekly', 'https://forefdn.org/grants-and-funding/'],
   ['Federal-CDC', 'CDC Overdose Data to Action (OD2A)', 'daily', 'https://www.cdc.gov/overdose-prevention/php/od2a/about.html'],
   ['Federal-DOJ', 'BJA COSSUP', 'daily', 'https://bja.ojp.gov/program/cossup/funding'],
   ['Federal-DoD', 'CDMRP PRMRP / CPMRP (pain, for-profit)', 'daily', 'https://cdmrp.health.mil/funding/prmrp'],
   ['Federal-DOL', 'ETA apprenticeship / WIOA ETPL', 'weekly', 'https://www.apprenticeship.gov/'],
   ['Payer', 'Medicaid 1115 SUD waivers', 'weekly', 'https://www.medicaid.gov/medicaid/section-1115-demonstrations/index.html'],
   ['Association', 'National Council / CCBHC-E · NACHC + PCAs · ASAM', 'weekly', 'https://www.thenationalcouncil.org/our-work/ccbhc/'],
   ['Research-CER', 'PCORI comparative-effectiveness PFAs (for-profit eligible)', 'weekly', 'https://www.pcori.org/funding-opportunities'],
   ['Research', 'AHRQ funding opportunities', 'weekly', 'https://www.ahrq.gov/funding/index.html'],
   ['Tribal', 'SAMHSA Tribal Opioid Response · IHS COIPP/SASP', 'weekly', 'https://www.samhsa.gov/tribal-affairs'],
   ['Justice', 'ONDCP + BJA drug-court TTA', 'weekly', 'https://bja.ojp.gov/'],
   ['Workforce-states', 'NY OMH · MA Workforce Training Fund · OR HOWTO · HRSA BHWET · SAMHSA PCSS', 'weekly', 'https://omh.ny.gov/omhweb/rfp/'],
   ['Settlement-national', 'KFF Payback tracker · Johns Hopkins dashboard', 'weekly', 'https://kffhealthnews.org/opioid-settlements/'],
   ['Settlement-county', 'Open-web county RFP sweep', 'weekly', '(WebSearch)'],
   ['Winners', 'USASpending SOR/RCORP awardees', 'monthly', 'https://www.usaspending.gov']
  ].forEach(function (r) { rows.push(r); });

  section('STATE AGENCY DIRECTORY — behavioral-health authority funding pages');
  rows.push(['state', 'agency', 'funding page', 'settlement page / notes']);
  var dir = STATE_DIRECTORY_CSV ? Utilities.parseCsv(STATE_DIRECTORY_CSV) : [];
  for (var i = 1; i < dir.length; i++) {
    rows.push([dir[i][0], dir[i][1], dir[i][2], (dir[i][3] || '') + (dir[i][4] ? ' — ' + dir[i][4] : '')]);
  }
  if (dir.length < 2) rows.push(['(directory payload pending — regenerate via scripts/generate.py)', '', '', '']);

  section('INSERT KITS');
  rows.push(['direct-template / line-item-kit / letter-of-support', 'kit_url column in Data_Auto links each row to its kit doc', '', '']);

  var width = 4;
  var norm = rows.map(function (r) { while (r.length < width) r.push(''); return r.slice(0, width); });
  sh.getRange(1, 1, norm.length, width).setValues(norm);
  sh.getRange(1, 1).setFontWeight('bold').setFontSize(12);
  for (var j = 0; j < norm.length; j++) {
    if (String(norm[j][0]).indexOf('—') === 0) sh.getRange(j + 1, 1, 1, width).setFontWeight('bold').setBackground('#eef1f7');
  }
  sh.setColumnWidth(1, 200); sh.setColumnWidth(2, 380); sh.setColumnWidth(3, 340); sh.setColumnWidth(4, 340);
}

// ————— Archive: expired/decided rows land here with a reason —————
function buildArchive(ss) {
  var sh = ss.getSheetByName('Archive') || ss.insertSheet('Archive');
  if (sh.getLastRow() === 0) {
    var headers = ['grant_id', 'name', 'funder', 'program', 'channel', 'state', 'path', 'forprofit_direct',
                   'category', 'accessible_usd', 'pool_usd', 'deadline', 'cycle_watch', 'likelihood', 'priority',
                   'heart', 'nofo_url', 'source_url', 'portal', 'accounts_needed', 'match_required', 'page_limit',
                   'attachments', 'scoring_map', 'effort_hrs', 'kit_type', 'kit_url', 'last_verified',
                   'next_check', 'found_date', 'archived_on', 'reason'];
    sh.getRange(1, 1, 1, headers.length).setValues([headers]).setFontWeight('bold');
    sh.setFrozenRows(1);
  }
}

/** Rail A switch: rebuild ONLY Data_Auto as a live IMPORTDATA feed. Leaves
 * Radar/Playbook/Team (and any human styling) untouched. */
function switchToRailA() {
  if (!RAW_CSV_URL) throw new Error('Set RAW_CSV_URL first.');
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var sh = ss.getSheetByName('Data_Auto');
  sh.clearContents();
  sh.getRange('A1').setFormula('=IMPORTDATA("' + RAW_CSV_URL + '")');
  SpreadsheetApp.flush();
  Logger.log('Data_Auto now feeds from ' + RAW_CSV_URL + ' (Google refreshes ~hourly). Run syncTeam() after it loads.');
}

/** Per-owner filter views on Radar via the Advanced Sheets Service (enable
 * "Google Sheets API" under Services first). Safe to re-run — skips existing. */
function addFilterViews() {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var sheetId = ss.getSheetByName('Radar').getSheetId();
  var existing = {};
  var meta = Sheets.Spreadsheets.get(ss.getId(), { fields: 'sheets(filterViews(title))' });
  (meta.sheets || []).forEach(function (s) {
    (s.filterViews || []).forEach(function (v) { existing[v.title] = true; });
  });
  var wanted = ['Jon', 'Asha', 'Dr. Garland', 'Rhea', 'Unassigned'];
  var requests = [];
  wanted.forEach(function (name) {
    if (existing[name]) return;
    var criteria = name === 'Unassigned'
      ? { condition: { type: 'BLANK' } }
      : { condition: { type: 'TEXT_EQ', values: [{ userEnteredValue: name }] } };
    requests.push({ addFilterView: { filter: {
      title: name,
      range: { sheetId: sheetId, startRowIndex: 2, endRowIndex: 1000, startColumnIndex: 0, endColumnIndex: 17 },
      criteria: { '12': criteria }
    } } });
  });
  if (requests.length) Sheets.Spreadsheets.batchUpdate({ requests: requests }, ss.getId());
  Logger.log('Filter views: ' + (requests.length ? requests.length + ' created' : 'all already present') +
    '. Owner names in Team must match exactly: Jon, Asha, Dr. Garland, Rhea.');
}

function orderTabs(ss) {
  ['Radar', 'Team', 'Playbook', 'Data_Auto', 'Archive'].forEach(function (name, i) {
    var sh = ss.getSheetByName(name);
    if (sh) { ss.setActiveSheet(sh); ss.moveActiveSheet(i + 1); }
  });
  ss.setActiveSheet(ss.getSheetByName('Radar'));
  var d = ss.getSheetByName('Sheet1');
  if (d && d.getLastRow() === 0) ss.deleteSheet(d);
}
