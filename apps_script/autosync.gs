// Daily Team-tab sync: the last manual step in the radar, now automatic.
// The radar adds new grant_ids to Data_Auto (IMPORTDATA of radar.csv) every day;
// this appends a Team row (status "New", blank owner) for each id the team hasn't
// seen yet, so new opportunities can be assigned without anyone running code.
// Install once: run installDailySync() from the Apps Script editor and approve.

var RADAR_SHEET_ID = '1Sd5QvUL1B_jwFHu4EsAjSTQeW67DBr4QJpxixb7YpT8';

// Trigger entry point. A time trigger passes an event object, so syncTeam(e)
// would treat the event as the spreadsheet; open the Sheet explicitly instead.
function syncTeamDaily() {
  syncTeam(SpreadsheetApp.openById(RADAR_SHEET_ID));
}

// Creates the daily trigger (7-8am in the script's time zone, after the radar's
// 4am PT rebuild and the hourly IMPORTDATA refresh). Safe to re-run: removes any
// earlier syncTeamDaily trigger first, then runs one sync immediately.
function installDailySync() {
  ScriptApp.getProjectTriggers().forEach(function (t) {
    if (t.getHandlerFunction() === 'syncTeamDaily') ScriptApp.deleteTrigger(t);
  });
  ScriptApp.newTrigger('syncTeamDaily').timeBased().everyDays(1).atHour(7).create();
  syncTeamDaily();
  Logger.log('Daily Team sync installed (runs ~7am). Triggers: ' + ScriptApp.getProjectTriggers().length);
}
