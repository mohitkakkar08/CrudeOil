Exit code: 0
Wall time: 0.5 seconds
Output:
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from crudeoil_chain.cache import ChainRow, ChainSnapshot, MarketTick
from crudeoil_chain.sheet import GoogleSheetGateway
from sensex_chain.sheet import WorkerStatus
from sensex_chain.timebox import KOLKATA


class Request:
    def __init__(self, callback): self._callback = callback
    def execute(self): self._callback()


class Values:
    def __init__(self, parent): self.parent = parent
    def batchUpdate(self, *, spreadsheetId, body):
        return Request(lambda: setattr(self.parent, "body", body))


class Spreadsheets:
    def __init__(self, parent): self.parent = parent
    def values(self): return Values(self.parent)


class Service:
    def __init__(self): self.body = {}
    def spreadsheets(self): return Spreadsheets(self)


def test_crudeoil_gateway_writes_chain_and_support_tab_formulas() -> None:
    service = Service()
    now = datetime(2026, 8, 12, 10, 0, tzinfo=KOLKATA)
    snapshot = ChainSnapshot(
        date(2026, 8, 19), now, MarketTick("MCX:CRUDEOIL26AUGFUT", ltp=6500), None,
        (ChainRow(Decimal("6500"), MarketTick("MCX:CRUDEOIL26AUG6500CE", ltp=100), MarketTick("MCX:CRUDEOIL26AUG6500PE", ltp=110)),),
        MarketTick("MCX:CRUDEOIL26AUGFUT", ltp=6500),
    )

    GoogleSheetGateway(service, "crude-sheet").write_snapshot(snapshot, WorkerStatus.connected(now))

    data = service.body["data"]
    assert data[0]["range"] == "CrudeOil!A1:AL4"
    assert data[1]["range"] == "CrudeOil!A6:AL7"
    support_ranges = [item["range"] for item in data[2:]]
    assert "CrudeOil LTP Run!A1:C7" in support_ranges
    assert "CrudeOil Rolling Data!A1:I2" in support_ranges

    ltp_values = next(item["values"] for item in data if item["range"] == "CrudeOil LTP Run!A1:C7")
    assert ltp_values[0][:2] == ["", ""]
    assert "TRANSPOSE(FILTER(CrudeOil!R7:R" in ltp_values[0][2]
    assert [row[:2] for row in ltp_values[1:]] == [
        ["LTP", "CE"], ["LTP", "PE"], ["OI", "CE"],
        ["OI", "PE"], ["COI", "CE"], ["COI", "PE"],
    ]

    rolling_values = next(item["values"] for item in data if item["range"] == "CrudeOil Rolling Data!A1:I2")
    assert rolling_values[0] == [
        "Rolling COI (5m)", "Rolling TOI (5m)", "Call OI (5m)", "Put OI (5m)",
        "Spot", "India VIX", "Straddle", "Snapshot Count", "Data Timestamp",
    ]
    assert "CrudeOil Records" in rolling_values[1][0]
    assert "CrudeOil Records" in rolling_values[1][4]
    assert "CrudeOil!Q7:Q" in ltp_values[1][2]
    assert "CrudeOil!S7:S" in ltp_values[2][2]
    assert "CrudeOil!K7:K" in ltp_values[3][2]
    assert "CrudeOil!X7:X" in ltp_values[4][2]
    assert "CrudeOil!L7:L" in ltp_values[5][2]
    assert "CrudeOil!W7:W" in ltp_values[6][2]

