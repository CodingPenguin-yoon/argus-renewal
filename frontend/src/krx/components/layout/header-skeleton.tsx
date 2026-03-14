import { Skeleton } from "@/components/ui/skeleton";

export function SharedMarketHeaderSkeleton() {
  return (
    <div className="mx-auto w-full max-w-6xl px-4 pt-6 md:pt-8">
      <div className="relative overflow-hidden rounded-[28px] border border-amber-200/18 bg-gradient-to-br from-slate-950 via-slate-900 to-stone-900 p-6 text-slate-100 shadow-xl">
        <div className="pointer-events-none absolute -right-12 -top-12 h-48 w-48 rounded-full bg-amber-200/10 blur-3xl" />
        <div className="pointer-events-none absolute -bottom-16 -left-10 h-44 w-44 rounded-full bg-white/6 blur-3xl" />

        <div className="relative flex flex-col gap-5">
          <div className="flex flex-col gap-4 xl:flex-row xl:items-start xl:justify-between">
            <div className="max-w-3xl space-y-3">
              <Skeleton className="h-4 w-40 bg-white/10" />
              <Skeleton className="h-9 w-48 bg-white/10" />
              <div className="space-y-2">
                <Skeleton className="h-5 w-full max-w-xl bg-white/10" />
                <Skeleton className="h-5 w-3/4 max-w-md bg-white/10" />
              </div>
            </div>

            <div className="flex flex-wrap items-center gap-2 xl:max-w-sm xl:justify-end">
              <Skeleton className="h-6 w-16 rounded-full bg-white/10" />
              <Skeleton className="h-6 w-20 rounded-full bg-white/10" />
              <Skeleton className="h-6 w-28 rounded-full bg-white/10" />
            </div>
          </div>

          <div className="flex flex-wrap gap-2">
            <Skeleton className="h-8 w-32 rounded-full bg-white/10" />
            <Skeleton className="h-8 w-40 rounded-full bg-white/10" />
            <Skeleton className="h-8 w-36 rounded-full bg-white/10" />
          </div>

          <div className="rounded-2xl border border-white/12 bg-white/6 px-4 py-3">
            <Skeleton className="h-3 w-24 bg-white/10" />
            <Skeleton className="mt-2 h-4 w-64 bg-white/10" />
            <div className="mt-3 flex flex-wrap gap-2">
              <Skeleton className="h-6 w-24 rounded-full bg-white/10" />
              <Skeleton className="h-6 w-20 rounded-full bg-white/10" />
              <Skeleton className="h-6 w-28 rounded-full bg-white/10" />
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
