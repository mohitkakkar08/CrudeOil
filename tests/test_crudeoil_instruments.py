from __future__ import annotations

from datetime import date
from decimal import Decimal

from crudeoil_chain.instruments import FyersInstrumentCatalog


def test_selects_current_crudeoil_options_and_future_independently() -> None:
    catalog = FyersInstrumentCatalog.from_csv("\n".join([
        "101,CRUDEOIL 19 Aug 26 6500 CE,11,20,1,,0900-2330:,2026-08-12,1787149800,MCX:CRUDEOIL26AUG6500CE,12,11,1,CRUDEOIL,1,6500,CE",
        "102,CRUDEOIL 19 Aug 26 6500 PE,11,20,1,,0900-2330:,2026-08-12,1787149800,MCX:CRUDEOIL26AUG6500PE,12,11,2,CRUDEOIL,1,6500,PE",
        "103,CRUDEOIL 20 Sep 26 6500 CE,11,20,1,,0900-2330:,2026-08-12,1789900000,MCX:CRUDEOIL26SEP6500CE,12,11,3,CRUDEOIL,1,6500,CE",
        "104,CRUDEOIL 20 Sep 26 6500 PE,11,20,1,,0900-2330:,2026-08-12,1789900000,MCX:CRUDEOIL26SEP6500PE,12,11,4,CRUDEOIL,1,6500,PE",
        "105,CRUDEOIL 17 Aug 26 FUT,11,20,1,,0900-2330:,2026-08-12,1786977000,MCX:CRUDEOIL26AUGFUT,12,11,5,CRUDEOIL,1,-1,XX",
        "106,CRUDEOIL 19 Sep 26 FUT,11,20,1,,0900-2330:,2026-08-12,1789823400,MCX:CRUDEOIL26SEPFUT,12,11,6,CRUDEOIL,1,-1,XX",
    ]))

    chain = catalog.current_crudeoil_chain(date(2026, 8, 12))

    assert chain.expiry == date(2026, 8, 19)
    assert chain.future is not None
    assert chain.future.expiry == date(2026, 8, 17)
    assert chain.future.symbol == "MCX:CRUDEOIL26AUGFUT"
    assert chain.strike_pairs[0][0] == Decimal("6500")
    assert chain.symbols[-1] == "MCX:CRUDEOIL26AUGFUT"

