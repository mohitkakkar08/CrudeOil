from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from crudeoil_chain.cache import LatestMarketCache
from crudeoil_chain.instruments import CurrentExpiryChain, FutureContract, OptionContract
from sensex_chain.timebox import KOLKATA


def _chain(future: FutureContract) -> CurrentExpiryChain:
    return CurrentExpiryChain(
        date(2026, 8, 19),
        (
            OptionContract("MCX:CRUDEOIL26AUG6500CE", "CRUDEOIL", date(2026, 8, 19), Decimal("6500"), "CE"),
            OptionContract("MCX:CRUDEOIL26AUG6500PE", "CRUDEOIL", date(2026, 8, 19), Decimal("6500"), "PE"),
        ),
        future,
    )


def test_snapshot_uses_separate_crudeoil_future_as_its_underlying() -> None:
    future = FutureContract("MCX:CRUDEOIL26AUGFUT", "CRUDEOIL", date(2026, 8, 17))
    chain = _chain(future)
    cache = LatestMarketCache()
    cache.upsert({"symbol": future.symbol, "ltp": 6501, "oi": 25000})

    snapshot = cache.snapshot(chain, datetime(2026, 8, 12, 10, 0, tzinfo=KOLKATA))

    assert snapshot.underlying.symbol == future.symbol
    assert snapshot.underlying.ltp == 6501
    assert snapshot.india_vix is None


def test_coverage_flags_future_stale_once_ltp_stops_refreshing() -> None:
    future = FutureContract("MCX:CRUDEOIL26AUGFUT", "CRUDEOIL", date(2026, 8, 17))
    clock = {"t": 0.0}
    cache = LatestMarketCache(monotonic=lambda: clock["t"])
    cache.upsert({"symbol": future.symbol, "ltp": 6501})

    assert cache.coverage(_chain(future), stale_after_seconds=30.0).future_stale is False
    clock["t"] = 31.0
    assert cache.coverage(_chain(future), stale_after_seconds=30.0).future_stale is True


def test_coverage_future_stale_ignores_oi_only_refreshes() -> None:
    """An OI-only update (the real future-depth enricher never carries a
    price) must not be mistaken for a fresh LTP and mask a socket that
    stopped ticking. Same root cause and fix as sensex_chain 0.2.0."""
    future = FutureContract("MCX:CRUDEOIL26AUGFUT", "CRUDEOIL", date(2026, 8, 17))
    clock = {"t": 0.0}
    cache = LatestMarketCache(monotonic=lambda: clock["t"])
    cache.upsert({"symbol": future.symbol, "ltp": 6501})
    clock["t"] = 31.0
    cache.upsert({"symbol": future.symbol, "oi": 25000, "oi_change": 800})

    assert cache.coverage(_chain(future), stale_after_seconds=30.0).future_stale is True


def test_coverage_has_future_tick_true_even_while_stale() -> None:
    """Presence and freshness are different questions: a stale future has
    ticked (so has_future_tick stays True) but is no longer fresh."""
    future = FutureContract("MCX:CRUDEOIL26AUGFUT", "CRUDEOIL", date(2026, 8, 17))
    clock = {"t": 0.0}
    cache = LatestMarketCache(monotonic=lambda: clock["t"])
    cache.upsert({"symbol": future.symbol, "ltp": 6501})
    clock["t"] = 31.0

    coverage = cache.coverage(_chain(future), stale_after_seconds=30.0)
    assert coverage.has_future_tick is True
    assert coverage.future_stale is True

