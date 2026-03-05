import Link from "next/link";

import { Badge } from "@/components/ui/badge";
import { IMPORTANCE_LABELS, SENTIMENT_LABELS } from "@/lib/constants";
import { formatKoreanDate } from "@/lib/utils";
import { News } from "@/types/domain";

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

export function NewsCard({ news }: { news: News }) {
  return (
    <article className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
      <div className="flex items-center gap-2 text-xs text-slate-500">
        <span>{news.source}</span>
        <span aria-hidden>•</span>
        <time dateTime={news.publishedAt}>{formatKoreanDate(news.publishedAt)}</time>
      </div>

      <h3 className="mt-2 text-base font-semibold leading-snug text-slate-900">
        <Link href={`/news/${news.id}`} className="hover:text-sky-700 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sky-500">
          {news.title}
        </Link>
      </h3>

      <p className="mt-2 text-sm text-slate-700">{news.summary}</p>

      <div className="mt-3 rounded-lg bg-sky-50 px-3 py-2 text-sm text-sky-900">
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
            href={`/stocks/${encodeURIComponent(ticker)}`}
            className="inline-flex rounded-full bg-slate-100 px-2.5 py-1 text-xs font-medium text-slate-700 hover:bg-slate-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sky-500"
          >
            {ticker}
          </Link>
        ))}
      </div>
    </article>
  );
}
