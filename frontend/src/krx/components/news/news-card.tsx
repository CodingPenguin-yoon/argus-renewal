import Link from "next/link";

import { Badge } from "@/krx/components/ui/badge";
import { IMPORTANCE_LABELS, SENTIMENT_LABELS } from "@/krx/lib/constants";
import { marketHref } from "@/krx/lib/market";
import { formatKoreanDate } from "@/krx/lib/utils";
import { MarketCode, News } from "@/krx/types/domain";

function sentimentVariant(sentiment: News["sentiment"]) {
  if (sentiment === "positive") return "positive";
  if (sentiment === "negative") return "negative";
  return "neutral";
}

function importanceVariant(importance: News["importance"]) {
  if (importance === "high") return "high";
  if (importance === "low") return "low";
  return "medium";
}

export function NewsCard({ market, news }: { market: MarketCode; news: News }) {
  return (
    <article className="rounded-2xl border border-slate-600/70 bg-gradient-to-br from-slate-800 to-slate-700 p-4 text-slate-100 shadow-sm transition hover:-translate-y-0.5 hover:shadow-md">
      <div className="flex items-center gap-2 text-xs text-slate-300/85">
        <span>{news.source}</span>
        <span aria-hidden>•</span>
        <time dateTime={news.publishedAt}>{formatKoreanDate(news.publishedAt)}</time>
      </div>

      <h3 className="mt-2 text-base font-semibold leading-snug text-slate-50">
        <Link
          href={marketHref(market, `/news/${news.id}`)}
          className="hover:text-amber-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-amber-200"
        >
          {news.title}
        </Link>
      </h3>

      <p className="mt-2 text-sm text-slate-200/90">{news.summary}</p>

      <div className="mt-3 rounded-xl border border-amber-200/20 bg-slate-800/55 px-3 py-2 text-sm text-amber-100">
        <p className="font-medium">왜 중요한가</p>
        <p className="mt-1">{news.whyItMatters}</p>
      </div>

      <div className="mt-3 flex flex-wrap items-center gap-2">
        <Badge variant={sentimentVariant(news.sentiment)}>{SENTIMENT_LABELS[news.sentiment]}</Badge>
        <Badge variant={importanceVariant(news.importance)}>{IMPORTANCE_LABELS[news.importance]}</Badge>
        <Badge>{news.category}</Badge>
        {news.relatedTickers.map((ticker) => (
          <Link
            key={`${news.id}-${ticker}`}
            href={marketHref(market, `/stocks/${encodeURIComponent(ticker)}`)}
            className="inline-flex rounded-full border border-slate-400/80 bg-slate-600/50 px-2.5 py-1 text-xs font-medium text-slate-100 transition hover:border-amber-200 hover:text-amber-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-amber-200"
          >
            {ticker}
          </Link>
        ))}
      </div>
    </article>
  );
}
