"""FYERS option-chain enrichment using the selected MCX Crude Oil future."""
from __future__ import annotations

from collections.abc import Callable

import requests

from sensex_chain.option_chain import OptionChainError, _is_rate_limited, _retry_after_seconds, _sdk_option_chain_model, extract_option_ticks
from sensex_chain.rate_limit import FyersRequestGate


class FyersCrudeOilOptionChainEnricher:
    def __init__(self, client_id: str, token: str, model_factory: Callable[[str, str], object] | None = None, request_gate: FyersRequestGate | None = None) -> None:
        self._client_id = client_id
        self._token = token
        self._model_factory = model_factory or _sdk_option_chain_model
        self._request_gate = request_gate or FyersRequestGate(minimum_interval_seconds=10.0)
        self._model: object | None = None
        self.diagnostic_code = "OPTION_CHAIN_NOT_STARTED"

    def refresh(self, chain, cache) -> None:
        if chain.future is None:
            self.diagnostic_code = "OPTION_CHAIN_NO_CURRENT_FUTURE"
            return
        permission = self._request_gate.acquire()
        if not permission.allowed:
            self.diagnostic_code = f"RATE_LIMIT_BACKOFF_{permission.retry_in_seconds}S"
            return
        try:
            response = self._client().optionchain(data={
                "symbol": chain.future.symbol,
                "strikecount": max(1, len(chain.strike_pairs)),
                "timestamp": "",
                "greeks": "1",
            })
            if _is_rate_limited(response):
                delay = self._request_gate.on_rate_limit(_retry_after_seconds(response))
                self.diagnostic_code = f"RATE_LIMIT_BACKOFF_{delay}S"
                return
            for tick in extract_option_ticks(response, chain.option_symbols).values():
                cache.upsert(tick)
            self._request_gate.on_success()
            self.diagnostic_code = "OPTION_CHAIN_OK"
        except OptionChainError as exc:
            self.diagnostic_code = str(exc)
        except requests.Timeout:
            self.diagnostic_code = "OPTION_CHAIN_TIMEOUT"
        except Exception:
            self.diagnostic_code = "OPTION_CHAIN_REQUEST_FAILED"

    def _client(self) -> object:
        if self._model is None:
            self._model = self._model_factory(self._client_id, self._token)
        return self._model

