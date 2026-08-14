"""Thread-safe latest-value cache for the MCX Crude Oil chain."""
from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from threading import Lock
from typing import Mapping

from .instruments import CurrentExpiryChain


@dataclass(frozen=True)
class MarketTick:
    symbol: str
    ltp: float | None = None
    prev_close: float | None = None
    open: float | None = None
    high: float | None = None
    low: float | None = None
    volume: float | None = None
    oi: float | None = None
    oi_change: float | None = None
    vwap: float | None = None
    iv: float | None = None
    delta: float | None = None
    gamma: float | None = None
    theta: float | None = None
    vega: float | None = None
    rho: float | None = None


@dataclass(frozen=True)
class ChainRow:
    strike: Decimal
    call: MarketTick
    put: MarketTick


@dataclass(frozen=True)
class ChainSnapshot:
    expiry: date
    updated_at: datetime
    underlying: MarketTick
    india_vix: MarketTick | None
    rows: tuple[ChainRow, ...]
    future: MarketTick | None


@dataclass(frozen=True)
class MarketDataCoverage:
    """Presence of a future tick (``has_future_tick``) only proves the
    future symbol ticked at least once. A socket can keep that first tick
    sitting in cache forever without ever refreshing it again, while CE/PE
    option data keeps flowing normally via the separate REST option-chain
    call. ``coverage()`` also reports whether the future's LTP has gone
    stale, so that condition is visible as a diagnostic instead of silently
    reading as "LIVE" (same root cause and fix as sensex_chain 0.2.0).
    """

    tick_count: int
    option_tick_count: int
    has_future_tick: bool
    future_stale: bool = False


class LatestMarketCache:
    def __init__(self, monotonic: Callable[[], float] = time.monotonic) -> None:
        self._lock = Lock()
        self._ticks: dict[str, MarketTick] = {}
        self._last_seen: dict[str, float] = {}
        self._last_price_seen: dict[str, float] = {}
        self._monotonic = monotonic

    def upsert(self, raw_tick: Mapping[str, object]) -> None:
        tick = _normalize_tick(raw_tick)
        if tick is None:
            return
        with self._lock:
            previous = self._ticks.get(tick.symbol)
            self._ticks[tick.symbol] = tick if previous is None else _merge_tick(previous, tick)
            now = self._monotonic()
            self._last_seen[tick.symbol] = now
            # Tracked separately from _last_seen: an OI-only REST update (the
            # future depth enricher below) touches _last_seen without ever
            # carrying a price, which would otherwise mask a socket that
            # stopped refreshing the LTP itself. Staleness must be judged on
            # price freshness, not on "something touched this symbol".
            if tick.ltp is not None:
                self._last_price_seen[tick.symbol] = now

    def coverage(self, chain: CurrentExpiryChain, stale_after_seconds: float = 30.0) -> MarketDataCoverage:
        now = self._monotonic()
        with self._lock:
            symbols = set(self._ticks)
            last_price_seen = dict(self._last_price_seen)
        option_symbols = chain.option_symbols
        has_future = chain.future is not None and chain.future.symbol in symbols
        future_stale = False
        if chain.future is not None:
            future_symbol = chain.future.symbol
            future_stale = future_symbol in last_price_seen and (now - last_price_seen[future_symbol]) > stale_after_seconds
        return MarketDataCoverage(len(symbols), len(symbols & option_symbols), has_future, future_stale)

    def snapshot(self, chain: CurrentExpiryChain, now: datetime) -> ChainSnapshot:
        with self._lock:
            ticks = dict(self._ticks)
        future = ticks.get(chain.future.symbol, MarketTick(chain.future.symbol)) if chain.future else None
        underlying = future or MarketTick("MCX:CRUDEOIL-FUT")
        rows = tuple(
            ChainRow(strike, ticks.get(call.symbol, MarketTick(call.symbol)), ticks.get(put.symbol, MarketTick(put.symbol)))
            for strike, call, put in chain.strike_pairs
        )
        return ChainSnapshot(chain.expiry, now, underlying, None, rows, future)


def _normalize_tick(raw_tick: Mapping[str, object]) -> MarketTick | None:
    symbol = str(raw_tick.get("symbol") or raw_tick.get("symbol_name") or "").strip()
    ltp = _number(raw_tick, "ltp", "lp")
    if not symbol or (raw_tick.get("ltp") is not None and ltp is None):
        return None
    return MarketTick(
        symbol, ltp, _number(raw_tick, "prev_close_price", "prev_close"),
        _number(raw_tick, "open_price", "open"), _number(raw_tick, "high_price", "high"),
        _number(raw_tick, "low_price", "low"), _number(raw_tick, "vol_traded_today", "volume"),
        _number(raw_tick, "oi", "OI", "open_interest"), _number(raw_tick, "oi_change", "OIch", "oich", "change_in_oi"),
        _number(raw_tick, "avg_trade_price", "vwap"), _number(raw_tick, "iv", "implied_volatility"),
        _number(raw_tick, "delta"), _number(raw_tick, "gamma"), _number(raw_tick, "theta"),
        _number(raw_tick, "vega"), _number(raw_tick, "rho"),
    )


def _number(raw_tick: Mapping[str, object], *keys: str) -> float | None:
    for key in keys:
        if raw_tick.get(key) not in (None, ""):
            try:
                return float(raw_tick[key])
            except (TypeError, ValueError):
                return None
    return None


def _merge_tick(previous: MarketTick, update: MarketTick) -> MarketTick:
    return MarketTick(**{
        field: getattr(update, field) if getattr(update, field) is not None else getattr(previous, field)
        for field in MarketTick.__dataclass_fields__
    })

