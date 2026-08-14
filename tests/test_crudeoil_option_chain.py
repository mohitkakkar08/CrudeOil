from datetime import date
from decimal import Decimal

from crudeoil_chain.cache import LatestMarketCache
from crudeoil_chain.instruments import CurrentExpiryChain, FutureContract, OptionContract
from crudeoil_chain.option_chain import FyersCrudeOilOptionChainEnricher
from sensex_chain.rate_limit import FyersRequestGate


def test_crudeoil_option_enricher_uses_selected_future_as_fyers_underlying() -> None:
    future = FutureContract("MCX:CRUDEOIL26AUGFUT", "CRUDEOIL", date(2026, 8, 17))
    chain = CurrentExpiryChain(date(2026, 8, 19), (
        OptionContract("MCX:CRUDEOIL26AUG6500CE", "CRUDEOIL", date(2026, 8, 19), Decimal("6500"), "CE"),
        OptionContract("MCX:CRUDEOIL26AUG6500PE", "CRUDEOIL", date(2026, 8, 19), Decimal("6500"), "PE"),
    ), future)

    class Client:
        def optionchain(self, *, data):
            self.data = data
            return {"s": "ok", "data": [{"symbol": "MCX:CRUDEOIL26AUG6500CE", "oi": 400, "iv": 22.1}]}

    client = Client()
    cache = LatestMarketCache()
    enricher = FyersCrudeOilOptionChainEnricher("client", "token", model_factory=lambda *_: client)

    enricher.refresh(chain, cache)

    assert client.data["symbol"] == "MCX:CRUDEOIL26AUGFUT"
    assert cache.snapshot(chain, __import__("datetime").datetime.now()).rows[0].call.oi == 400


def _crudeoil_chain() -> CurrentExpiryChain:
    return CurrentExpiryChain(date(2026, 8, 19), (
        OptionContract("MCX:CRUDEOIL26AUG6500CE", "CRUDEOIL", date(2026, 8, 19), Decimal("6500"), "CE"),
        OptionContract("MCX:CRUDEOIL26AUG6500PE", "CRUDEOIL", date(2026, 8, 19), Decimal("6500"), "PE"),
    ), FutureContract("MCX:CRUDEOIL26AUGFUT", "CRUDEOIL", date(2026, 8, 17)))


def test_option_enricher_reports_routine_pacing_as_throttled_not_rate_limited() -> None:
    """The gate's own minimum-interval pacing (flush_seconds sitting right on
    top of the 10s gate) is not a FYERS failure. It must produce a distinct
    OPTION_CHAIN_THROTTLED_ code, matching the FUTURE_DEPTH_THROTTLED_
    precedent, not the generic RATE_LIMIT_BACKOFF_ used for a real 429."""
    chain = _crudeoil_chain()

    class Client:
        def optionchain(self, *, data):
            raise AssertionError("must not call FYERS while the gate says not-yet")

    gate = FyersRequestGate(monotonic=lambda: 0.0, minimum_interval_seconds=10.0)
    gate.acquire()  # first call consumes the slot; now_allowed_at = 10.0
    enricher = FyersCrudeOilOptionChainEnricher("client", "token", model_factory=lambda *_: Client(), request_gate=gate)

    enricher.refresh(chain, LatestMarketCache())

    assert enricher.diagnostic_code.startswith("OPTION_CHAIN_THROTTLED_")


def test_option_enricher_reports_real_429_as_rate_limit_backoff() -> None:
    """A genuine FYERS 429 (only known after actually calling the API) must
    still surface as a real, unhealthy diagnostic — it must not be
    accidentally swept up by the THROTTLED whitelist."""
    chain = _crudeoil_chain()

    class Client:
        def optionchain(self, *, data):
            return {"s": "error", "code": "429", "message": "rate limit exceeded"}

    enricher = FyersCrudeOilOptionChainEnricher("client", "token", model_factory=lambda *_: Client())

    enricher.refresh(chain, LatestMarketCache())

    assert enricher.diagnostic_code.startswith("OPTION_CHAIN_RATE_LIMIT_BACKOFF_")

