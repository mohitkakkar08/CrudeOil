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

