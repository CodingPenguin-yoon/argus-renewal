import { Badge } from "@/components/ui/badge";
import { IMPORTANCE_LABELS } from "@/lib/constants";
import { formatKoreanDate } from "@/lib/utils";
import { MarketEvent } from "@/types/domain";

export function EventCard({ event }: { event: MarketEvent }) {
  const variant = event.impactLevel === "high" ? "high" : event.impactLevel === "low" ? "low" : "medium";

  return (
    <article className="rounded-xl border border-slate-200 bg-white p-4">
      <div className="flex items-center justify-between gap-3">
        <h3 className="text-sm font-semibold text-slate-900">{event.title}</h3>
        <Badge variant={variant}>{IMPORTANCE_LABELS[event.impactLevel]}</Badge>
      </div>
      <p className="mt-2 text-sm text-slate-700">{event.description}</p>
      <p className="mt-2 text-xs text-slate-500">
        {event.country} · {formatKoreanDate(event.eventDate)}
      </p>
    </article>
  );
}
