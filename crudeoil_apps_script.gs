Exit code: 0
Wall time: 0.4 seconds
Output:
// CrudeOil option-chain dashboard and recorder.
// This is the SENSEX recorder model mapped to the MCX CrudeOil workbook.
const SPREADSHEET_ID = '1-Z5TwzXgNqYd75y8g3TdWTLMiICMMeXoRfxzjxkSpb8';
const LIVE_SHEET = 'Sheet1';
const FEED_SHEET = 'CrudeOil';
const LTP_SHEET = 'CrudeOil LTP Run';
const ROLLING_SHEET = 'CrudeOil Rolling Data';
const RECORDS_SHEET = 'CrudeOil Records';

const CE_SOURCE_ROW = 2;
const CE_COLUMNS = 114;                 // A:DJ
const PE_SOURCE_ROW = 3;
const STRIKE_GRID_START_COLUMN = 54;    // BB
const PE_COLUMNS = 61;                  // BB:DJ
const TOTAL_COLUMNS = 175;              // A:FS
const STATIC_HEADER_COLUMNS = 53;       // A:BA
const RECORD_HEADER_ROW = 6;
const RECORD_START_ROW = 7;

function book_() {
  return SpreadsheetApp.openById(SPREADSHEET_ID);
}

function ensureGrid_(sheet, columns, rows) {
  if (sheet.getMaxColumns() < columns) {
    sheet.insertColumnsAfter(sheet.getMaxColumns(), columns - sheet.getMaxColumns());
  }
  if (sheet.getMaxRows() < rows) {
    sheet.insertRowsAfter(sheet.getMaxRows(), rows - sheet.getMaxRows());
  }
}

// Safe and idempotent: it creates the hidden record mirror and restores the
// SENSEX-style horizontal LTP helper. It deliberately never clears or replaces
// the customized Sheet1 or Rolling Data formula model.
function setupCrudeOilWorkbook() {
  const ss = book_();
  const live = ss.getSheetByName(LIVE_SHEET);
  const feed = ss.getSheetByName(FEED_SHEET);
  if (!live || !feed) throw new Error('Required sheets are missing. Need Sheet1 and CrudeOil.');
  ensureGrid_(live, TOTAL_COLUMNS, RECORD_START_ROW);
  ensureCrudeOilRecords_(ss);
  setupCrudeOilLtpRun_(ss);
  SpreadsheetApp.flush();
}

function ensureCrudeOilRecords_(ss) {
  // Sheet5 was created by the initial workbook bootstrap. Rename it in place
  // so formulas already using it continue to point to the same record table.
  let records = ss.getSheetByName(RECORDS_SHEET);
  const temporary = ss.getSheetByName('Sheet5');
  if (!records && temporary) {
    temporary.setName(RECORDS_SHEET);
    records = temporary;
  }
  if (!records) records = ss.insertSheet(RECORDS_SHEET);
  ensureGrid_(records, TOTAL_COLUMNS, RECORD_START_ROW);
  records.getRange('A1').setFormula('=Sheet1!A6:FS');
  records.hideSheet();
}

function setupCrudeOilLtpRun_(ss) {
  const sheet = ss.getSheetByName(LTP_SHEET) || ss.insertSheet(LTP_SHEET);
  // MCX can expose well above 61 strikes. Clear a generous horizontal area,
  // then use dynamic spill formulas so every live strike is shown.
  ensureGrid_(sheet, 702, 7); // A:ZZ
  sheet.getRange('A1:ZZ7').clearContent();
  sheet.getRange('A2:B7').setValues([
    ['LTP', 'CE'],
    ['LTP', 'PE'],
    ['OI', 'CE'],
    ['OI', 'PE'],
    ['COI', 'CE'],
    ['COI', 'PE']
  ]);
  const formulaFor = column => `=IFERROR(TRANSPOSE(FILTER(${FEED_SHEET}!${column}7:${column},${FEED_SHEET}!R7:R<>"",${FEED_SHEET}!R7:R<>0)),"")`;
  sheet.getRange('C1:C7').setFormulas([
    [formulaFor('R')], [formulaFor('Q')], [formulaFor('S')], [formulaFor('K')],
    [formulaFor('X')], [formulaFor('L')], [formulaFor('W')]
  ]);
  sheet.setFrozenColumns(2);
}

// One-minute Apps Script triggers support two writes per minute through a
// 30-second pause. flush() is essential: it commits the first snapshot before
// the pause instead of batching both rows together at the end.
function recordCrudeOilSnapshot() {
  recordCrudeOilSnapshot_(false);
  Utilities.sleep(30 * 1000);
  recordCrudeOilSnapshot_(false);
}

function testCrudeOilRecorder() {
  recordCrudeOilSnapshot_(true);
}

function recordCrudeOilSnapshot_(allowOutsideMarket) {
  const ss = book_();
  const live = ss.getSheetByName(LIVE_SHEET);
  const feed = ss.getSheetByName(FEED_SHEET);
  if (!live) throw new Error('Missing live dashboard sheet: ' + LIVE_SHEET);
  if (!feed) throw new Error('Missing raw feed sheet: ' + FEED_SHEET);
  ensureGrid_(live, TOTAL_COLUMNS, RECORD_START_ROW);

  const tz = ss.getSpreadsheetTimeZone();
  const now = new Date();
  const weekday = Number(Utilities.formatDate(now, tz, 'u'));
  const hhmm = Utilities.formatDate(now, tz, 'HHmm');
  const isMarketSession = weekday <= 5 && hhmm >= '0900' && hhmm <= '2330';
  if (!allowOutsideMarket && !isMarketSession) return;

  const status = String(feed.getRange('B4').getDisplayValue() || '');
  const diagnostic = String(feed.getRange('D4').getDisplayValue() || '');
  if (!allowOutsideMarket && status !== 'LIVE') {
    throw new Error('Skipped snapshot: live status is ' + status + '; diagnostic: ' + diagnostic);
  }

  const staticHeaders = live.getRange(1, 1, 1, STATIC_HEADER_COLUMNS).getDisplayValues()[0];
  const staticHeaderRange = live.getRange(RECORD_HEADER_ROW, 1, 1, STATIC_HEADER_COLUMNS);
  if (staticHeaderRange.getDisplayValues()[0].every(value => value === '')) {
    staticHeaderRange.setValues([staticHeaders]);
  }

  const ceValues = live.getRange(CE_SOURCE_ROW, 1, 1, CE_COLUMNS).getValues()[0];
  const peValues = live.getRange(PE_SOURCE_ROW, STRIKE_GRID_START_COLUMN, 1, PE_COLUMNS).getValues()[0];
  const nextRow = Math.max(RECORD_START_ROW, live.getLastRow() + 1);
  live.getRange(nextRow, 1, 1, TOTAL_COLUMNS).setValues([ceValues.concat(peValues)]);
  SpreadsheetApp.flush();
}

function installCrudeOilMinuteRecorder() {
  ScriptApp.getProjectTriggers()
    .filter(trigger => trigger.getHandlerFunction() === 'recordCrudeOilSnapshot')
    .forEach(trigger => ScriptApp.deleteTrigger(trigger));
  ScriptApp.newTrigger('recordCrudeOilSnapshot').timeBased().everyMinutes(1).create();
}

function clearCrudeOilRecords() {
  const live = book_().getSheetByName(LIVE_SHEET);
  if (live) live.getRange('A7:FS999').clearContent();
}

