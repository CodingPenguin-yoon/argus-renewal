from __future__ import annotations

import argparse
import json
from datetime import datetime

from ..config.env import get_settings
from .market_flow.adapters import FixtureMarketFlowAdapter, FixtureProviderError, FixtureScenario
from .market_flow.collect import collect_market_flow
from .market_flow.repository import SQLiteMarketFlowRepository


def _parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise argparse.ArgumentTypeError("--as-of must include a timezone offset")
    return parsed


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="market-data")
    subparsers = parser.add_subparsers(dest="command", required=True)
    seed = subparsers.add_parser(
        "seed-market-flow-fixture",
        help="Store deterministic mock market-flow facts",
    )
    seed.add_argument(
        "--scenario",
        choices=[scenario.value for scenario in FixtureScenario],
        default=FixtureScenario.NORMAL.value,
    )
    seed.add_argument("--as-of", type=_parse_datetime, default=None)
    seed.add_argument("--db-path", default=None)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command != "seed-market-flow-fixture":
        return 2

    settings = get_settings()
    repository = SQLiteMarketFlowRepository(args.db_path or settings.db_path)
    provider = FixtureMarketFlowAdapter(scenario=FixtureScenario(args.scenario))
    try:
        result = collect_market_flow(
            provider=provider,
            writer=repository,
            as_of=args.as_of,
        )
    except FixtureProviderError as exc:
        print(json.dumps({"status": "error", "error": str(exc)}, ensure_ascii=False))
        return 1

    print(
        json.dumps(
            {
                "status": "ok",
                "data_mode": result.data_mode.value,
                "fetched_count": result.fetched_count,
                "inserted_count": result.inserted_count,
                "db_path": repository.db_path,
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
