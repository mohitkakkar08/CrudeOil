from datetime import date
from decimal import Decimal

from crudeoil_chain.cache import LatestMarketCache
from crudeoil_chain.instruments import CurrentExpiryChain, FutureContract, OptionContract
from crudeoil_chain.option_chain import FyersCrudeOilOptionChainEnricher


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

