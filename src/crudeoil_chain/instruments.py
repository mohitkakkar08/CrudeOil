"""FYERS MCX derivatives-master parsing and current-expiry Crude Oil selection."""
from __future__ import annotations

import csv
import io
import re
from dataclasses import dataclass
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from functools import cached_property
from typing import Iterable, Sequence


INSTRUMENT_MASTER_URL = "https://public.fyers.in/sym_details/MCX_COM.csv"
UNDERLYING = "CRUDEOIL"


class InstrumentDiscoveryError(ValueError):
    pass


@dataclass(frozen=True)
class OptionContract:
    symbol: str
    underlying: str
    expiry: date
    strike: Decimal
    option_type: str


@dataclass(frozen=True)
class FutureContract:
    symbol: str
    underlying: str
    expiry: date


@dataclass(frozen=True)
class CurrentExpiryChain:
    expiry: date
    contracts: tuple[OptionContract, ...]
    future: FutureContract | None

    @cached_property
    def symbols(self) -> tuple[str, ...]:
        future = (self.future.symbol,) if self.future else ()
        return tuple(contract.symbol for contract in self.contracts) + future

    @cached_property
    def option_symbols(self) -> frozenset[str]:
        return frozenset(contract.symbol for contract in self.contracts)

    @cached_property
    def strike_pairs(self) -> tuple[tuple[Decimal, OptionContract, OptionContract], ...]:
        by_strike: dict[Decimal, dict[str, OptionContract]] = {}
        for contract in self.contracts:
            by_strike.setdefault(contract.strike, {})[contract.option_type] = contract
        return tuple(
            (strike, pair["CE"], pair["PE"])
            for strike, pair in sorted(by_strike.items())
            if "CE" in pair and "PE" in pair
        )


class FyersInstrumentCatalog:
    def __init__(self, contracts: Iterable[OptionContract], futures: Iterable[FutureContract] = ()) -> None:
        self._contracts = tuple(contracts)
        self._futures = tuple(futures)

    @classmethod
    def from_csv(cls, contents: str) -> "FyersInstrumentCatalog":
        rows = list(csv.reader(io.StringIO(contents)))
        if not rows:
            raise InstrumentDiscoveryError("INSTRUMENT_MASTER_EMPTY")
        contracts: list[OptionContract] = []
        futures: list[FutureContract] = []
        for row in rows:
            option = _parse_option(row)
            future = _parse_future(row)
            if option:
                contracts.append(option)
            if future:
                futures.append(future)
        return cls(contracts, futures)

    @classmethod
    def download(cls, http: object) -> "FyersInstrumentCatalog":
        try:
            response = http.get(INSTRUMENT_MASTER_URL, timeout=30)
            response.raise_for_status()
            return cls.from_csv(response.text)
        except InstrumentDiscoveryError:
            raise
        except Exception:
            raise InstrumentDiscoveryError("INSTRUMENT_MASTER_DOWNLOAD") from None

    def current_crudeoil_chain(self, today: date) -> CurrentExpiryChain:
        candidates = [item for item in self._contracts if item.underlying == UNDERLYING and item.expiry >= today]
        if not candidates:
            raise InstrumentDiscoveryError("INSTRUMENT_MASTER_NO_CRUDEOIL_OPTIONS")
        futures = [item for item in self._futures if item.underlying == UNDERLYING and item.expiry >= today]
        future = min(futures, key=lambda item: (item.expiry, item.symbol)) if futures else None
        for expiry in sorted({item.expiry for item in candidates}):
            contracts = tuple(sorted((item for item in candidates if item.expiry == expiry), key=lambda item: (item.strike, item.option_type, item.symbol)))
            if {"CE", "PE"}.issubset({item.option_type for item in contracts}):
                return CurrentExpiryChain(expiry, contracts, future)
        raise InstrumentDiscoveryError("INSTRUMENT_MASTER_NO_VALID_EXPIRY")


def chunk_subscriptions(symbols: Sequence[str], max_symbols: int = 200) -> list[list[str]]:
    if max_symbols < 1:
        raise ValueError("max_symbols must be positive")
    return [list(symbols[index:index + max_symbols]) for index in range(0, len(symbols), max_symbols)]


def _parse_option(row: list[str]) -> OptionContract | None:
    if len(row) < 17 or row[13].strip().upper() != UNDERLYING or row[16].strip().upper() not in {"CE", "PE"}:
        return None
    strike = row[15].strip()
    if not strike:
        match = re.search(r"\s(\d+(?:\.\d+)?)\s+(CE|PE)\s*$", row[1].strip(), re.I)
        strike = match.group(1) if match else ""
    try:
        return OptionContract(
            row[9].strip(),
            UNDERLYING,
            datetime.fromtimestamp(int(float(row[8])), tz=timezone.utc).date(),
            Decimal(strike),
            row[16].strip().upper(),
        )
    except (IndexError, InvalidOperation, ValueError):
        return None


def _parse_future(row: list[str]) -> FutureContract | None:
    if len(row) < 14 or row[13].strip().upper() != UNDERLYING or not row[9].strip().upper().endswith("FUT"):
        return None
    try:
        return FutureContract(row[9].strip(), UNDERLYING, datetime.fromtimestamp(int(float(row[8])), tz=timezone.utc).date())
    except (IndexError, ValueError):
        return None

