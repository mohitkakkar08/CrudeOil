from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from crudeoil_chain.cache import LatestMarketCache
from crudeoil_chain.instruments import CurrentExpiryChain, FutureContract, OptionContract
from crudeoil_chain.timebox import MCX_KOLKATA, SessionSegment
from crudeoil_chain.worker import LiveChainWorker


class Catalog:
    def current_crudeoil_chain(self, today: date) -> CurrentExpiryChain:
        future = FutureContract("MCX:CRUDEOIL26AUGFUT", "CRUDEOIL", date(2026, 8, 17))
        return CurrentExpiryChain(date(2026, 8, 19), (
            OptionContract("MCX:CRUDEOIL26AUG6500CE", "CRUDEOIL", date(2026, 8, 19), Decimal("6500"), "CE"),
            OptionContract("MCX:CRUDEOIL26AUG6500PE", "CRUDEOIL", date(2026, 8, 19), Decimal("6500"), "PE"),
        ), future)


class TokenProvider:
    def access_token(self) -> str: return "token"


class Feed:
    def __init__(self) -> None: self.stopped = False
    def start(self, symbols, on_tick) -> None:
        on_tick({"symbol": "MCX:CRUDEOIL26AUGFUT", "ltp": 6500})
        on_tick({"symbol": "MCX:CRUDEOIL26AUG6500CE", "ltp": 100})
    def stop(self) -> None: self.stopped = True


class Clock:
    def now(self): return datetime(2026, 8, 12, 10, 0, tzinfo=MCX_KOLKATA)
    def monotonic(self): return 0.0
    def sleep(self, seconds): pass


class Gateway:
    def write_snapshot(self, snapshot, status):
        self.snapshot, self.status = snapshot, status


def test_crudeoil_worker_writes_one_live_snapshot_and_stops_feed() -> None:
    feed, gateway = Feed(), Gateway()
    worker = LiveChainWorker(Catalog(), TokenProvider(), lambda _: feed, LatestMarketCache(), gateway, Clock(), 10)

    assert worker.run(SessionSegment.MORNING, max_cycles=1) == 0
    assert gateway.snapshot.underlying.symbol == "MCX:CRUDEOIL26AUGFUT"
    assert gateway.status.state == "LIVE"
    assert feed.stopped is True


class StaleFuturePriceFeed:
    """Ticks the future once at t=0, then never refreshes its LTP again —
    reproducing the silent-freeze bug: options and OI keep flowing while
    the future's price is frozen."""

    def __init__(self) -> None:
        self.stopped = False

    def start(self, symbols, on_tick) -> None:
        on_tick({"symbol": "MCX:CRUDEOIL26AUGFUT", "ltp": 6500})
        on_tick({"symbol": "MCX:CRUDEOIL26AUG6500CE", "ltp": 100})

    def stop(self) -> None:
        self.stopped = True


class OiOnlyFutureDepthEnricher:
    """Stands in for the real future-depth enricher: refreshes OI every
    cycle but never carries a price, so it must not be read as a fresh
    LTP touch."""

    diagnostic_code = "FUTURE_DEPTH_OK"

    def refresh(self, chain, cache) -> None:
        cache.upsert({"symbol": chain.future.symbol, "oi": 25000, "oi_change": 800})


def test_crudeoil_worker_surfaces_future_tick_stale_instead_of_live() -> None:
    """Same bug and fix as sensex_chain 0.2.0: a frozen future price must
    not silently read as LIVE just because it ticked once and OI keeps
    refreshing via REST. Cycle 1 (t=0) is correctly fresh; cycle 2 (t=31,
    after the sleep between cycles) must flip to PARTIAL_LIVE/FUTURE_TICK_STALE
    even though OI kept refreshing every cycle in between."""
    clock = {"t": 0.0}

    class FakeClock(Clock):
        def sleep(self, seconds: float) -> None:
            clock["t"] += 31.0  # simulate the real 31s gap in one test step

        def monotonic(self) -> float:
            return clock["t"]

    class HistoryGateway(Gateway):
        def __init__(self) -> None:
            self.history: list = []

        def write_snapshot(self, snapshot, status) -> None:
            super().write_snapshot(snapshot, status)
            self.history.append(status)

    feed, gateway = StaleFuturePriceFeed(), HistoryGateway()
    cache = LatestMarketCache(monotonic=lambda: clock["t"])
    worker = LiveChainWorker(
        Catalog(), TokenProvider(), lambda _: feed, cache, gateway, FakeClock(), 10,
        future_depth_factory=lambda _: OiOnlyFutureDepthEnricher(),
    )

    assert worker.run(SessionSegment.MORNING, max_cycles=2) == 0

    assert gateway.history[0].state == "LIVE"  # cycle 1 (t=0): future just ticked, correctly fresh
    assert gateway.history[1].state == "PARTIAL_LIVE"
    assert gateway.history[1].diagnostic_code == "FUTURE_TICK_STALE"

