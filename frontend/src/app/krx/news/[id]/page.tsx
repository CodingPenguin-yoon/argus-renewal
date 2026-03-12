import Link from "next/link";
import { notFound } from "next/navigation";

import { DisclaimerBanner } from "@/krx/components/layout/disclaimer-banner";
import { Badge } from "@/krx/components/ui/badge";
import { SectionHeader } from "@/krx/components/ui/section-header";
import { IMPORTANCE_LABELS, SENTIMENT_LABELS } from "@/krx/lib/constants";
import { NewsCard } from "@/krx/news/components/news-card";
import { getNewsDetail } from "@/krx/server/data-service";
import { formatKoreanDate } from "@/krx/lib/utils";

export default async function KrxNewsDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const detail = await getNewsDetail(id);

  if (!detail) notFound();

  const { item, related } = detail;

  return (
    <div className="mx-auto flex w-full max-w-4xl flex-col gap-6 px-4 py-6">
      <DisclaimerBanner />

      <article className="rounded-2xl border border-slate-200 bg-white p-5">
        <p className="text-sm text-slate-500">
          {item.source} · {formatKoreanDate(item.publishedAt)}
        </p>
        <h1 className="mt-2 text-2xl font-bold leading-snug text-slate-900">{item.title}</h1>

        <div className="mt-3 flex flex-wrap gap-2">
          <Badge
            variant={
              item.sentiment === "positive" ? "positive" : item.sentiment === "negative" ? "negative" : "neutral"
            }
          >
            {SENTIMENT_LABELS[item.sentiment]}
          </Badge>
          <Badge variant={item.importance === "high" ? "high" : item.importance === "low" ? "low" : "medium"}>
            {IMPORTANCE_LABELS[item.importance]}
          </Badge>
          <Badge>{item.category}</Badge>
        </div>

        <section className="mt-5 space-y-3 text-sm text-slate-800">
          <div>
            <h2 className="font-semibold text-slate-900">요약</h2>
            <p className="mt-1">{item.summary}</p>
          </div>
          <div className="rounded-xl bg-sky-50 p-3">
            <h2 className="font-semibold text-sky-900">왜 중요한가</h2>
            <p className="mt-1 text-sky-900">{item.whyItMatters}</p>
          </div>
          <div>
            <h2 className="font-semibold text-slate-900">관련 섹터/종목</h2>
            <p className="mt-1">섹터: {item.relatedSectors.join(", ")}</p>
            <p className="mt-1">종목: {item.relatedTickers.join(", ") || "없음"}</p>
          </div>
          <div>
            <h2 className="font-semibold text-slate-900">원문 출처</h2>
            <Link
              href={item.sourceUrl}
              target="_blank"
              rel="noreferrer"
              className="mt-1 inline-flex text-sky-700 underline underline-offset-2"
            >
              {item.source} 원문 보기
            </Link>
          </div>
        </section>
      </article>

      <section className="space-y-4">
        <SectionHeader title="같은 이슈 연관 뉴스" />
        <div className="grid gap-4">
          {related.map((news) => (
            <NewsCard key={news.id} market="krx" news={news} />
          ))}
        </div>
      </section>
    </div>
  );
}
