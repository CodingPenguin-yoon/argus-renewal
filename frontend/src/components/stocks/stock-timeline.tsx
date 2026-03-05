import { formatKoreanDate } from "@/lib/utils";
import { News } from "@/types/domain";

export function StockTimeline({ items }: { items: News[] }) {
  return (
    <ol className="space-y-4">
      {items.map((news) => (
        <li key={news.id} className="relative rounded-xl border border-slate-200 bg-white p-4 pl-6">
          <span className="absolute left-2.5 top-6 h-2 w-2 rounded-full bg-sky-600" aria-hidden />
          <p className="text-xs text-slate-500">{formatKoreanDate(news.publishedAt)}</p>
          <p className="mt-1 text-sm font-semibold text-slate-900">{news.title}</p>
          <p className="mt-1 text-sm text-slate-700">{news.whyItMatters}</p>
        </li>
      ))}
    </ol>
  );
}
