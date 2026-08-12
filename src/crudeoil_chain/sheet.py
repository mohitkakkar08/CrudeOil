Exit code: 0
Wall time: 0.7 seconds
Output:
"""Google Sheets output for MCX Crude Oil and its support tabs."""
from __future__ import annotations

import json
from typing import Any

from sensex_chain.sheet import (
    CHAIN_HEADERS, FUTURE_HEADERS, WIDTH, SheetGatewayError, WorkerStatus,
    _cell, _change, _change_percent, _future_values, _oi_change_percent, _pad, _timestamp,
)

from .cache import ChainSnapshot


SHEET_NAME = "CrudeOil"


class GoogleSheetGateway:
    def __init__(self, sheets_service: Any, sheet_id: str) -> None:
        self._sheets = sheets_service
        self._sheet_id = sheet_id
        self._headers_written = False
        self._support_written = False

    @classmethod
    def from_service_account_json(cls, service_account_json: str, sheet_id: str) -> "GoogleSheetGateway":
        try:
            from google.oauth2 import service_account
            from googleapiclient.discovery import build
            credentials = service_account.Credentials.from_service_account_info(
                json.loads(service_account_json), scopes=["https://www.googleapis.com/auth/spreadsheets"]
            )
            return cls(build("sheets", "v4", credentials=credentials, cache_discovery=False), sheet_id)
        except Exception as exc:
            raise SheetGatewayError("SHEET_AUTHORIZATION_FAILED") from exc

    def write_snapshot(self, snapshot: ChainSnapshot, status: WorkerStatus) -> None:
        headers = not self._headers_written
        chain_values = _chain_values(snapshot, headers)
        data = [
            {"range": f"{SHEET_NAME}!A1:AL4", "values": _summary_values(snapshot, status)},
            {"range": f"{SHEET_NAME}!A{6 if headers else 7}:AL{6 + len(chain_values) - 1 if headers else 6 + len(chain_values)}", "values": chain_values},
        ]
        if not self._support_written:
            data.extend(_support_tab_values())
        try:
            self._sheets.spreadsheets().values().batchUpdate(
                spreadsheetId=self._sheet_id, body={"valueInputOption": "USER_ENTERED", "data": data}
            ).execute()
            self._headers_written = True
            self._support_written = True
        except Exception as exc:
            raise SheetGatewayError("SHEET_WRITE_FAILED") from exc


def _summary_values(snapshot: ChainSnapshot, status: WorkerStatus) -> list[list[object]]:
    future = snapshot.future or snapshot.underlying
    return [
        _pad(["Instrument", "Prev Close", "Open", "High", "Low", "LTP", "LTP Change", "LTP Change %", "", "", "", *FUTURE_HEADERS]),
        _pad([snapshot.underlying.symbol, _cell(snapshot.underlying.prev_close), _cell(snapshot.underlying.open), _cell(snapshot.underlying.high), _cell(snapshot.underlying.low), _cell(snapshot.underlying.ltp), _change(snapshot.underlying), _change_percent(snapshot.underlying), "", "", "", *_future_values(future)]),
        _pad(["India VIX", ""]),
        _pad(["Status", status.state, "Diagnostic", status.diagnostic_code, "Ticks", status.tick_count, "Option Ticks", status.option_tick_count, "Options Expiry", snapshot.expiry.isoformat(), "Updated", _timestamp(status.updated_at)]),
    ]


def _chain_values(snapshot: ChainSnapshot, include_headers: bool) -> list[list[object]]:
    values = [list(CHAIN_HEADERS)] if include_headers else []
    for row in snapshot.rows:
        c, p = row.call, row.put
        values.append([
            _cell(c.prev_close), _cell(c.low), _cell(c.high), _cell(c.open), _cell(c.rho), _cell(c.theta), _cell(c.vega), _cell(c.gamma), _cell(c.delta), _cell(c.iv), _cell(c.oi), _cell(c.oi_change), _oi_change_percent(c), _cell(c.volume), _change(c), _change_percent(c), _cell(c.ltp), float(row.strike), _cell(p.ltp), _change(p), _change_percent(p), _cell(p.volume), _cell(p.oi_change), _cell(p.oi), _oi_change_percent(p), _cell(p.iv), _cell(p.delta), _cell(p.gamma), _cell(p.vega), _cell(p.theta), _cell(p.rho), _cell(p.open), _cell(p.high), _cell(p.low), _cell(p.prev_close), _timestamp(snapshot.updated_at), _cell(c.vwap), _cell(p.vwap),
        ])
    return values


def _support_tab_values() -> list[dict[str, object]]:
    # Match the SENSEX helper's horizontal strike-ladder layout.  MCX needs
    # 61 strike columns rather than the SENSEX sheet's 50, hence A:BK.
    ltp = [["", "", '=IFERROR(TRANSPOSE(FILTER(CrudeOil!R7:R,CrudeOil!R7:R<>"",CrudeOil!R7:R<>0)),"")'] + [""] * 60]
    labels = [("LTP", "CE"), ("LTP", "PE"), ("OI", "CE"), ("OI", "PE"), ("COI", "CE"), ("COI", "PE")]
    formulas = [
        '=IFERROR(TRANSPOSE(FILTER(CrudeOil!Q7:Q,CrudeOil!R7:R<>"",CrudeOil!R7:R<>0)),"")',
        '=IFERROR(TRANSPOSE(FILTER(CrudeOil!S7:S,CrudeOil!R7:R<>"",CrudeOil!R7:R<>0)),"")',
        '=IFERROR(TRANSPOSE(FILTER(CrudeOil!K7:K,CrudeOil!R7:R<>"",CrudeOil!R7:R<>0)),"")',
        '=IFERROR(TRANSPOSE(FILTER(CrudeOil!X7:X,CrudeOil!R7:R<>"",CrudeOil!R7:R<>0)),"")',
        '=IFERROR(TRANSPOSE(FILTER(CrudeOil!L7:L,CrudeOil!R7:R<>"",CrudeOil!R7:R<>0)),"")',
        '=IFERROR(TRANSPOSE(FILTER(CrudeOil!W7:W,CrudeOil!R7:R<>"",CrudeOil!R7:R<>0)),"")',
    ]
    ltp.extend([[metric, side, formula] + [""] * 60 for (metric, side), formula in zip(labels, formulas)])
    # SENSEX Rolling Data uses only this nine-field summary.  Keep the
    # instrument-specific detail in the live tab rather than maintaining a
    # second, incompatible rolling-data layout.
    rolling_headers = ["Rolling COI (5m)", "Rolling TOI (5m)", "Call OI (5m)", "Put OI (5m)", "Spot", "India VIX", "Straddle", "Snapshot Count", "Data Timestamp"]
    rolling_formulas = ['=IFERROR(SUM(CrudeOil!L7:L)+SUM(CrudeOil!W7:W),"")', '=IFERROR(SUM(CrudeOil!K7:K)+SUM(CrudeOil!X7:X),"")', '=IFERROR(SUM(CrudeOil!K7:K),"")', '=IFERROR(SUM(CrudeOil!X7:X),"")', '=IFERROR(CrudeOil!F2,"")', '=""', '=""', '=IFERROR(COUNTA(FILTER(CrudeOil!R7:R,CrudeOil!R7:R<>"")),"")', '=IFERROR(CrudeOil!AJ7,"")']
    return [
        {"range": "CrudeOil LTP Run!A1:BK7", "values": ltp},
        {"range": "CrudeOil Rolling Data!A1:I2", "values": [rolling_headers, rolling_formulas]},
    ]

