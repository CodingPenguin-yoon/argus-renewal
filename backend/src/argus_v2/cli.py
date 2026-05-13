from __future__ import annotations

import argparse
import json
from datetime import date
from typing import Sequence

from ..config.env import get_settings
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

    news_ai_parser = subparsers.add_parser("smoke-news-ai", help="Run one AI news enrichment request without storing data.")
    news_ai_parser.add_argument("--title", default="FOMC 금리 경계와 환율 상승")
    news_ai_parser.add_argument("--summary", default="미국 국채금리와 달러 강세가 위험자산에 부담입니다.")
    news_ai_parser.add_argument("--source", default="argus.smoke.news")
    news_ai_parser.add_argument("--source-url", default="https://example.test/news-ai-smoke")

    args = parser.parse_args(argv)
    settings = get_settings()
    if args.db_path:
        settings = settings.model_copy(update={"db_path": args.db_path})

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


if __name__ == "__main__":
    raise SystemExit(main())
