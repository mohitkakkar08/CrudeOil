"""Command-line entry point for the MCX Crude Oil sheet worker."""
from __future__ import annotations

import argparse
import os
import time
from datetime import datetime

import requests

from sensex_chain.auth import AuthenticationError, AutomatedFyersTokenProvider, FallbackTokenProvider, FyersTokenProvider
from sensex_chain.config import ConfigurationError, RuntimeConfig
from sensex_chain.future_depth import FyersFutureDepthEnricher
from sensex_chain.sheet import SheetGatewayError
from sensex_chain.socket import DataFeedError, FyersDataFeed

from .cache import LatestMarketCache
from .instruments import FyersInstrumentCatalog, InstrumentDiscoveryError
from .option_chain import FyersCrudeOilOptionChainEnricher
from .sheet import GoogleSheetGateway
from .timebox import MCX_KOLKATA, SessionSegment
from .worker import LiveChainWorker


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Stream current-expiry MCX Crude Oil options to Google Sheets")
    parser.add_argument("--segment", required=True, choices=["morning", "afternoon", "evening"])
    parser.add_argument("--once", action="store_true", help="Write one snapshot for a manual smoke test")
    parser.add_argument("--dry-run", action="store_true", help="Validate CLI wiring without market-data or Sheets requests")
    parser.add_argument("--debug-ticks", action="store_true", help="Print the first five websocket ticks")
    return parser


class SystemClock:
    def now(self) -> datetime:
        return datetime.now(MCX_KOLKATA)

    def monotonic(self) -> float:
        return time.monotonic()

    def sleep(self, seconds: float) -> None:
        time.sleep(seconds)


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.dry_run:
        print(f"Diagnostic: DRY_RUN; segment={args.segment}; no FYERS or Google Sheets request will be made.")
        return 0
    try:
        config = RuntimeConfig.from_environ(os.environ)
        print("Diagnostic: CONFIGURATION_READY")
        http = requests.Session()
        catalog = FyersInstrumentCatalog.download(http)
        print("Diagnostic: MCX_INSTRUMENT_CATALOG_READY")
        gateway = GoogleSheetGateway.from_service_account_json(config.google_service_account_json, config.sheet_id)
        print("Diagnostic: GOOGLE_SHEETS_GATEWAY_READY")
        automated = AutomatedFyersTokenProvider(config, http, lambda: int(time.time()))
        fallback = FyersTokenProvider(config, http) if config.fyers_refresh_token else None
        worker = LiveChainWorker(
            catalog,
            FallbackTokenProvider(automated, fallback),
            lambda token: FyersDataFeed(f"{config.fyers_client_id}:{token}"),
            LatestMarketCache(),
            gateway,
            SystemClock(),
            config.flush_seconds,
            option_chain_factory=lambda token: FyersCrudeOilOptionChainEnricher(config.fyers_client_id, token),
            future_depth_factory=lambda token: FyersFutureDepthEnricher(config.fyers_client_id, token),
        )
        print("Diagnostic: FYERS_AUTHENTICATION_STARTING")
        result = worker.run(SessionSegment.parse(args.segment), max_cycles=1 if args.once else None)
        print("Diagnostic: WORKER_STOPPED_CLEANLY")
        return result
    except ConfigurationError as exc:
        print(f"Diagnostic: CONFIGURATION_ERROR; {exc}")
        return 2
    except (AuthenticationError, InstrumentDiscoveryError, DataFeedError, SheetGatewayError) as exc:
        print(f"Diagnostic: {exc}")
        return 3
    except Exception as exc:
        print(f"Diagnostic: UNEXPECTED_{type(exc).__name__.upper()}")
        return 3

