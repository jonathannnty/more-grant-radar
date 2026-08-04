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
 * and re-run setup() — Data_Auto becomes a live IMPORTDATA feed (Google refreshes
 * roughly hourly). Leave it blank to use the embedded seed snapshot (Rail B).
 */

var RAW_CSV_URL = '';

// ——— payloads injected by scripts/generate.py — do not hand-edit ———
// <<RADAR_CSV>>
var SEED_RADAR_CSV = "grant_id,name,funder,program,channel,state,path,forprofit_direct,category,accessible_usd,pool_usd,deadline,cycle_watch,likelihood,priority,heart,nofo_url,source_url,portal,accounts_needed,match_required,page_limit,attachments,scoring_map,effort_hrs,kit_type,kit_url,last_verified,next_check,found_date\nsm-26-014,\"CCBHC Planning, Development & Implementation (SM-26-014)\",SAMHSA,Certified Community Behavioral Health Clinics PDI,Federal-discretionary,US,Line-item,N,MAT-MOUD,9400000,94000000,2026-08-17,,3,20.9,\"94 CCBHCs are writing applications right now \u2014 MORE goes in as their evidence-based line item and strengthens their scoring. Nonprofits and local government only, so this is a pure partner play: the insert kit goes out before the 17th.\",https://www.samhsa.gov/grants/grant-announcements/sm-26-014,https://www.grants.gov/search-results-detail/360977,Grants.gov (partners apply; MORE rides as line item),Partner needs SAM/UEI + Grants.gov,,,,\"MORE evidence (59% dropout reduction, ~3x CBT) strengthens the evidence-based-practices section of a CCBHC application\",20,line-item-kit,,2026-08-04,2026-08-05,2026-08-01\npa-27-100,NIH/NIDA SBIR Phase I (PA-27-100),NIH / NIDA,Parent SBIR (R43/R44) Clinical Trial Optional,Federal-discretionary,US,Direct,Y,SUD,400000,,2026-09-08,,5,28.0,\"The one big pot built for for-profits \u2014 R&D money for the MORE app and training platform. Eric wants the ~$2M path; Phase I is the door, first standard due date Sep 8.\",https://simpler.grants.gov/opportunity/d1ba49e5-3684-4420-849a-ab2330ec493e,https://www.grants.gov/search-results-detail/359671,Grants.gov / NIH ASSIST,\"SAM/UEI + eRA Commons \u2014 register now, takes weeks\",None,,,NIDA caps: Phase I $400K / Phase II $3M. Cycle recurs Jan 5 / Apr 5; parent open through 2027-04-05.,120,direct-template,,2026-08-04,2026-08-05,2026-08-01\nhrsa-rcorp-fy27,HRSA RCORP \u2014 FY27 cycle,HRSA,Rural Communities Opioid Response Program,Federal-discretionary,US,Direct,Y,SUD,750000,60000000,,2027-04-01,4,23.5,\"For-profits are explicitly eligible \u2014 rare for federal treatment money. FY26 closed in June; FY27 expected around May. Prep now, apply day one.\",https://simpler.grants.gov/opportunity/e779b908-4f8c-48ce-9485-1345475cdbaf,https://www.hrsa.gov/rural-health/grants/rural-communities-opioid-response,Grants.gov,SAM/UEI + Grants.gov,,,,FY26 shape: Planning $100K \u00d7 40 \u00b7 Impact $60M ~80 awards $750K min,60,direct-template,,2026-08-01,2026-08-11,2026-08-01\ntx-oafc-core-2026f,Texas OAFC \u2014 Fall 2026 CORE grants,TX Opioid Abatement Fund Council,CORE grant cycle,Settlement-state,TX,Direct/Sub,Y,SUD,500000,,,2026-09-15,4,22.8,\"Settlement money with provider-friendly eligibility, opening this fall. Watch page and GovDelivery list are live; position before it posts.\",,https://comptroller.texas.gov/programs/opioid-council/grants/grant-opp.php,Texas OGMS,TX OGMS account; TX SmartBuy/CMBL ($70/yr) for vendor path,,,,,40,direct-template,,2026-08-01,2026-08-11,2026-08-01\noneohio-c3,OneOhio Recovery Foundation \u2014 Cycle 3,OneOhio Recovery Foundation,Regional grant cycle 3,Settlement-state,OH,Direct,Y,SUD,500000,,,2026-11-15,3,17.1,For-profits eligible; Cycle 2 was $45.7M. Roughly annual \u2014 verify More Therapy's 2-year Ohio registration now so eligibility is ready when it opens.,,https://www.oneohiofoundation.com/grants,OneOhio application portal,Ohio SoS registration 2+ yrs,,,,Cycle 2 pattern: RFP Dec 10 \u2192 inquiry Jan 14\u2013Feb 11 \u2192 awards mid-year,40,direct-template,,2026-08-01,2026-08-11,2026-08-01\nallegheny-osf-2026,Allegheny County OSF \u2014 annual RFP,Allegheny County DHS,Opioid Settlement Fund RFP,Settlement-county,PA,Direct/Sub,Y,SUD,400000,,,2026-11-15,3,16.8,\"Annual county settlement RFP \u2014 opens around November, due January. Calendar it; the county pattern of 3\u20136-week windows is the volume play nationwide.\",,https://solicitations.alleghenycounty.us/,Bonfire,Bonfire vendor account (free),,,,,30,direct-template,,2026-08-01,2026-08-11,2026-08-01\nva-oaa-fy28,Virginia OAA \u2014 FY28 city & county cycle,VA Opioid Abatement Authority,City & county grants,Settlement-state,VA,Sub,N,SUD,200000,,,2026-09-01,2,10.6,Only Virginia localities can apply \u2014 MORE rides in as their named training vendor. Annual cycle; pitch localities while they draft.,,https://www.oaa.virginia.gov/portal-grants/,VA OAA portal (localities); eVA vendor registration (free) for MORE,Virginia eVA (free),,,,,20,letter-of-support,,2026-08-01,2026-08-11,2026-08-01\n";
// <<END_RADAR_CSV>>
// <<DIRECTORY_CSV>>
var STATE_DIRECTORY_CSV = "";
// <<END_DIRECTORY_CSV>>

var DATA_COLS = 30; // Data_Auto schema width (A..AD)
var STATUS_LIST = ['New', 'Reviewing', 'Pursuing-Direct', 'Pursuing-Sub', 'Submitted', 'Won', 'Lost', 'Passed'];

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

  var prot = sh.protect().setDescription('View tab — formulas only. Statuses/owners live in Team.');
  prot.setWarningOnly(true);
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
   ['Foundation', 'FORE', 'weekly', 'https://forefdn.org/grants-and-funding/'],
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

function orderTabs(ss) {
  ['Radar', 'Team', 'Playbook', 'Data_Auto', 'Archive'].forEach(function (name, i) {
    var sh = ss.getSheetByName(name);
    if (sh) { ss.setActiveSheet(sh); ss.moveActiveSheet(i + 1); }
  });
  ss.setActiveSheet(ss.getSheetByName('Radar'));
  var d = ss.getSheetByName('Sheet1');
  if (d && d.getLastRow() === 0) ss.deleteSheet(d);
}
