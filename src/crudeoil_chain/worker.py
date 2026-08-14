"""Bounded MCX Crude Oil WebSocket-to-Sheets supervisor."""
from __future__ import annotations

from collections.abc import Callable

from sensex_chain.sheet import SheetGatewayError, WorkerStatus

from .cache import LatestMarketCache, MarketDataCoverage
from .timebox import SessionSegment, seconds_remaining


class LiveChainWorker:
    def __init__(self, catalog, token_provider, feed_factory: Callable[[str], object], cache: LatestMarketCache, gateway, clock, flush_seconds: int, option_chain_factory=None, future_depth_factory=None, stale_after_seconds: float = 30.0) -> None:
        self._catalog = catalog
        self._token_provider = token_provider
        self._feed_factory = feed_factory
        self._cache = cache
        self._gateway = gateway
        self._clock = clock
        self._flush_seconds = flush_seconds
        self._option_chain_factory = option_chain_factory
        self._future_depth_factory = future_depth_factory
        self._stale_after_seconds = stale_after_seconds

    def run(self, segment: SessionSegment, max_cycles: int | None = None) -> int:
        now = self._clock.now()
        if seconds_remaining(now, segment) <= 0:
            return 0
        chain = self._catalog.current_crudeoil_chain(now.date())
        token = self._token_provider.access_token()
        feed = self._feed_factory(token)
        option_chain = self._option_chain_factory(token) if self._option_chain_factory else None
        future_depth = self._future_depth_factory(token) if self._future_depth_factory else None
        next_flush_at = self._clock.monotonic()
        try:
            feed.start(chain.symbols, self._cache.upsert)
            cycles = 0
            while seconds_remaining(self._clock.now(), segment) > 0:
                option_diagnostic = "OPTION_CHAIN_DISABLED"
                if option_chain:
                    option_chain.refresh(chain, self._cache)
                    option_diagnostic = getattr(option_chain, "diagnostic_code", "OPTION_CHAIN_OK")
                future_diagnostic = "FUTURE_DEPTH_DISABLED"
                if future_depth:
                    future_depth.refresh(chain, self._cache)
                    future_diagnostic = getattr(future_depth, "diagnostic_code", "FUTURE_DEPTH_OK")
                coverage = self._cache.coverage(chain, self._stale_after_seconds)
                status = self._status(now, coverage, option_diagnostic, future_diagnostic)
                try:
                    self._gateway.write_snapshot(self._cache.snapshot(chain, self._clock.now()), status)
                except SheetGatewayError:
                    pass
                cycles += 1
                if max_cycles is not None and cycles >= max_cycles:
                    return 0
                next_flush_at = self._sleep_until(next_flush_at, segment)
            return 0
        finally:
            feed.stop()

    def _status(self, now, coverage: MarketDataCoverage, option_diagnostic: str, future_diagnostic: str) -> WorkerStatus:
        if coverage.tick_count == 0:
            return WorkerStatus.waiting_for_ticks(now, "SOCKET_SUBSCRIBED_NO_TICKS")
        if not coverage.has_future_tick or coverage.option_tick_count == 0:
            return WorkerStatus.partial_live(now, coverage.tick_count, coverage.option_tick_count)
        if option_diagnostic not in {"OPTION_CHAIN_OK", "OPTION_CHAIN_DISABLED"} and not option_diagnostic.startswith("OPTION_CHAIN_THROTTLED_"):
            return WorkerStatus("PARTIAL_LIVE", now, option_diagnostic, coverage.tick_count, coverage.option_tick_count)
        future_depth_healthy = future_diagnostic in {"FUTURE_DEPTH_OK", "FUTURE_DEPTH_DISABLED", "FUTURE_DEPTH_NOT_APPLICABLE"} or future_diagnostic.startswith("FUTURE_DEPTH_THROTTLED_")
        if not future_depth_healthy:
            return WorkerStatus("PARTIAL_LIVE", now, future_diagnostic, coverage.tick_count, coverage.option_tick_count)
        if coverage.future_stale:
            return WorkerStatus("PARTIAL_LIVE", now, "FUTURE_TICK_STALE", coverage.tick_count, coverage.option_tick_count)
        return WorkerStatus.live(now, coverage.tick_count, coverage.option_tick_count)

    def _sleep_until(self, previous: float, segment: SessionSegment) -> float:
        deadline = previous + self._flush_seconds
        while deadline <= self._clock.monotonic():
            deadline += self._flush_seconds
        wait = min(deadline - self._clock.monotonic(), seconds_remaining(self._clock.now(), segment))
        if wait > 0:
            self._clock.sleep(wait)
        return deadline

