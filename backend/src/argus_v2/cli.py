from __future__ import annotations

import argparse
import json
from datetime import date, datetime, timezone
from typing import Sequence

from ..config.env import get_settings
from .collector import iter_collect_loop, run_collect_once
from .providers.context_inputs import run_context_collection, run_news_ai_smoke
from .providers.kis_live import run_kis_live_smoke


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m src.argus_v2.cli")
    subparsers = parser.add_subparsers(dest="command", required=True)

    smoke_parser = subparsers.add_parser("smoke-kis", help="Fetch KIS derivatives/options and persist v2 samples.")
    smoke_parser.add_argument("--trade-date", help="Trade date in YYYY-MM-DD. Defaults to today's KST date.")
    smoke_parser.add_argument("--db-path", help="Override DB_PATH for this run.")
    smoke_parser.add_argument("--token-cache-path", help="Override local KIS token cache path.")
    smoke_parser.add_argument("--skip-derivatives", action="store_true")
    smoke_parser.add_argument("--skip-option-chain", action="store_true")

    context_parser = subparsers.add_parser("collect-context", help="Collect v2 market reaction and news trigger inputs.")
    context_parser.add_argument("--trade-date", help="Trade date in YYYY-MM-DD. Defaults to today's KST date.")
    context_parser.add_argument("--db-path", help="Override DB_PATH for this run.")
    context_parser.add_argument("--skip-market-reaction", action="store_true")
    context_parser.add_argument("--skip-news-triggers", action="store_true")
    context_parser.add_argument("--market-reaction-provider", help="Override ARGUS_MARKET_REACTION_PROVIDER.")
    context_parser.add_argument("--news-triggers-provider", help="Override ARGUS_NEWS_TRIGGERS_PROVIDER.")

    collect_once_parser = subparsers.add_parser("collect-once", help="Run one session-aware collector pass.")
    collect_once_parser.add_argument("--trade-date", help="Override collector trading date in YYYY-MM-DD.")
    collect_once_parser.add_argument("--snapshot-time", help="Override snapshot time as ISO datetime.")
    collect_once_parser.add_argument("--db-path", help="Override DB_PATH for this run.")
    collect_once_parser.add_argument("--token-cache-path", help="Override local KIS token cache path.")
    collect_once_parser.add_argument("--market-only", action="store_true")
    collect_once_parser.add_argument("--news-only", action="store_true")
    collect_once_parser.add_argument("--force-market", action="store_true")
    collect_once_parser.add_argument("--skip-derivatives", action="store_true")
    collect_once_parser.add_argument("--skip-option-chain", action="store_true")
    collect_once_parser.add_argument("--skip-futures-flow", action="store_true")
    collect_once_parser.add_argument("--market-reaction-provider", help="Override ARGUS_MARKET_REACTION_PROVIDER.")
    collect_once_parser.add_argument("--news-triggers-provider", help="Override ARGUS_NEWS_TRIGGERS_PROVIDER.")

    collect_loop_parser = subparsers.add_parser("collect-loop", help="Run the session-aware collector repeatedly.")
    collect_loop_parser.add_argument("--db-path", help="Override DB_PATH for this run.")
    collect_loop_parser.add_argument("--token-cache-path", help="Override local KIS token cache path.")
    collect_loop_parser.add_argument("--market-only", action="store_true")
    collect_loop_parser.add_argument("--news-only", action="store_true")
    collect_loop_parser.add_argument("--force-market", action="store_true")
    collect_loop_parser.add_argument("--skip-derivatives", action="store_true")
    collect_loop_parser.add_argument("--skip-option-chain", action="store_true")
    collect_loop_parser.add_argument("--skip-futures-flow", action="store_true")
    collect_loop_parser.add_argument("--market-reaction-provider", help="Override ARGUS_MARKET_REACTION_PROVIDER.")
    collect_loop_parser.add_argument("--news-triggers-provider", help="Override ARGUS_NEWS_TRIGGERS_PROVIDER.")
    collect_loop_parser.add_argument("--interval-seconds", type=float, help="Seconds to sleep between collector passes.")
    collect_loop_parser.add_argument("--max-iterations", type=int, default=0, help="Stop after N iterations. Defaults to 0, meaning run until interrupted.")
    collect_loop_parser.add_argument("--collector-key", help="Override collector lease key.")
    collect_loop_parser.add_argument("--lease-ttl-seconds", type=float, help="Collector lease TTL. Defaults to ARGUS_COLLECTOR_LEASE_TTL_SECONDS.")

    news_ai_parser = subparsers.add_parser("smoke-news-ai", help="Run one AI news enrichment request without storing data.")
    news_ai_parser.add_argument("--title", default="FOMC 금리 경계와 환율 상승")
    news_ai_parser.add_argument("--summary", default="미국 국채금리와 달러 강세가 위험자산에 부담입니다.")
    news_ai_parser.add_argument("--source", default="Reuters")
    news_ai_parser.add_argument("--source-url", default="https://www.reuters.com/markets/rates-bonds/")

    args = parser.parse_args(argv)
    settings = get_settings()
    db_path = getattr(args, "db_path", None)
    if db_path:
        settings = settings.model_copy(update={"db_path": db_path})

    if args.command == "smoke-kis":
        result = run_kis_live_smoke(
            settings=settings,
            trade_date=date.fromisoformat(args.trade_date) if args.trade_date else None,
            include_derivatives=not args.skip_derivatives,
            include_option_chain=not args.skip_option_chain,
            token_cache_path=args.token_cache_path,
        )
        print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
        return 1 if any(provider.status == "failed" for provider in result.providers) else 0

    if args.command == "collect-context":
        result = run_context_collection(
            settings=settings,
            trade_date=date.fromisoformat(args.trade_date) if args.trade_date else None,
            include_market_reaction=not args.skip_market_reaction,
            include_news_triggers=not args.skip_news_triggers,
            market_reaction_provider=args.market_reaction_provider,
            news_triggers_provider=args.news_triggers_provider,
        )
        print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
        return 1 if any(provider.status == "failed" for provider in result.providers) else 0

    if args.command == "collect-once":
        result = run_collect_once(
            settings=settings,
            trade_date=date.fromisoformat(args.trade_date) if args.trade_date else None,
            snapshot_time=_parse_datetime(args.snapshot_time) if args.snapshot_time else None,
            include_market=not args.news_only,
            include_news=not args.market_only,
            force_market=args.force_market,
            include_derivatives=not args.skip_derivatives,
            include_option_chain=not args.skip_option_chain,
            include_futures_investor_flow=not args.skip_futures_flow,
            market_reaction_provider=args.market_reaction_provider,
            news_triggers_provider=args.news_triggers_provider,
            token_cache_path=args.token_cache_path,
        )
        print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
        return 1 if any(provider.status == "failed" for provider in result.providers) else 0

    if args.command == "collect-loop":
        exit_code = 0
        interval_seconds = args.interval_seconds
        if interval_seconds is None:
            interval_seconds = settings.argus_collector_loop_interval_seconds
        for result in iter_collect_loop(
            settings=settings,
            interval_seconds=interval_seconds,
            max_iterations=args.max_iterations,
            include_market=not args.news_only,
            include_news=not args.market_only,
            force_market=args.force_market,
            include_derivatives=not args.skip_derivatives,
            include_option_chain=not args.skip_option_chain,
            include_futures_investor_flow=not args.skip_futures_flow,
            market_reaction_provider=args.market_reaction_provider,
            news_triggers_provider=args.news_triggers_provider,
            token_cache_path=args.token_cache_path,
            collector_key=args.collector_key,
            lease_ttl_seconds=args.lease_ttl_seconds or settings.argus_collector_lease_ttl_seconds,
        ):
            print(json.dumps(result.to_dict(), ensure_ascii=False), flush=True)
            if hasattr(result, "providers") and any(provider.status == "failed" for provider in result.providers):
                exit_code = 1
        return exit_code

    if args.command == "smoke-news-ai":
        result = run_news_ai_smoke(
            settings=settings,
            title=args.title,
            summary=args.summary,
            source=args.source,
            source_url=args.source_url,
        )
        print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
        return 1 if result.status == "failed" else 0

    return 1


def _parse_datetime(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


if __name__ == "__main__":
    raise SystemExit(main())
