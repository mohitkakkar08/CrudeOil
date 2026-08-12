from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from crudeoil_chain.cache import LatestMarketCache
from crudeoil_chain.instruments import CurrentExpiryChain, FutureContract, OptionContract
from sensex_chain.timebox import KOLKATA


def test_snapshot_uses_separate_crudeoil_future_as_its_underlying() -> None:
    future = FutureContract("MCX:CRUDEOIL26AUGFUT", "CRUDEOIL", date(2026, 8, 17))
    chain = CurrentExpiryChain(
        date(2026, 8, 19),
        (
            OptionContract("MCX:CRUDEOIL26AUG6500CE", "CRUDEOIL", date(2026, 8, 19), Decimal("6500"), "CE"),
            OptionContract("MCX:CRUDEOIL26AUG6500PE", "CRUDEOIL", date(2026, 8, 19), Decimal("6500"), "PE"),
        ),
        future,
    )
    cache = LatestMarketCache()
    cache.upsert({"symbol": future.symbol, "ltp": 6501, "oi": 25000})

    snapshot = cache.snapshot(chain, datetime(2026, 8, 12, 10, 0, tzinfo=KOLKATA))

    assert snapshot.underlying.symbol == future.symbol
    assert snapshot.underlying.ltp == 6501
    assert snapshot.india_vix is None

