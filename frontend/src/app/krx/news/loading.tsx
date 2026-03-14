function SkeletonLine({ width }: { width: string }) {
  return <div className={`h-3 animate-pulse rounded-full bg-slate-200 ${width}`} />;
}

function SkeletonCard({ compact = false }: { compact?: boolean }) {
  return (
    <article className={`rounded-[24px] border border-slate-200 bg-white/90 p-4 ${compact ? "" : "shadow-[0_16px_40px_rgba(15,23,42,0.06)]"}`}>
      <div className="flex flex-wrap gap-2">
        <div className="h-6 w-16 animate-pulse rounded-full bg-slate-200" />
        <div className="h-6 w-20 animate-pulse rounded-full bg-slate-100" />
        <div className="h-6 w-28 animate-pulse rounded-full bg-slate-100" />
      </div>
      <div className="mt-4 space-y-3">
        <SkeletonLine width="w-4/5" />
        <SkeletonLine width="w-full" />
        <SkeletonLine width="w-3/4" />
      </div>
      <div className="mt-5 grid gap-3 md:grid-cols-2">
        <div className="rounded-2xl bg-slate-50 p-4">
          <div className="h-2.5 w-24 animate-pulse rounded-full bg-slate-200" />
          <div className="mt-3 space-y-2">
            <SkeletonLine width="w-full" />
            <SkeletonLine width="w-5/6" />
          </div>
        </div>
        <div className="rounded-2xl bg-slate-50 p-4">
          <div className="h-2.5 w-24 animate-pulse rounded-full bg-slate-200" />
          <div className="mt-3 space-y-2">
            <SkeletonLine width="w-full" />
            <SkeletonLine width="w-2/3" />
          </div>
        </div>
      </div>
    </article>
  );
}

export default function Loading() {
  return (
    <div className="mx-auto flex min-h-[75vh] w-full max-w-6xl flex-col gap-8 px-4 py-6 md:py-8">
      <section className="rounded-[36px] border border-slate-200 bg-[linear-gradient(140deg,rgba(255,255,255,0.98),rgba(241,245,249,0.94))] p-6 shadow-[0_24px_56px_rgba(15,23,42,0.08)]">
        <div className="space-y-3">
          <div className="h-3 w-32 animate-pulse rounded-full bg-slate-200" />
          <div className="h-10 w-24 animate-pulse rounded-full bg-slate-200" />
          <SkeletonLine width="w-full" />
          <SkeletonLine width="w-2/3" />
        </div>
        <div className="mt-5 flex flex-wrap gap-2">
          <div className="h-8 w-24 animate-pulse rounded-full bg-white" />
          <div className="h-8 w-24 animate-pulse rounded-full bg-white" />
          <div className="h-8 w-20 animate-pulse rounded-full bg-white" />
          <div className="h-8 w-36 animate-pulse rounded-full bg-white" />
        </div>
        <div className="mt-5 flex gap-2 overflow-hidden">
          <div className="h-9 w-16 animate-pulse rounded-full bg-amber-100" />
          <div className="h-9 w-24 animate-pulse rounded-full bg-slate-100" />
          <div className="h-9 w-24 animate-pulse rounded-full bg-slate-100" />
          <div className="h-9 w-16 animate-pulse rounded-full bg-slate-100" />
        </div>
      </section>

      <div className="grid gap-5 xl:grid-cols-[minmax(0,1.45fr)_minmax(300px,0.9fr)]">
        <section className="grid gap-5">
          <div className="rounded-[32px] border border-slate-200/90 bg-[linear-gradient(145deg,rgba(255,255,255,0.96),rgba(241,245,249,0.9))] p-5 shadow-[0_18px_44px_rgba(15,23,42,0.05)]">
            <div className="mb-4 flex items-start justify-between gap-3">
              <div className="space-y-2">
                <div className="h-6 w-48 animate-pulse rounded-full bg-slate-200" />
                <SkeletonLine width="w-72" />
              </div>
              <div className="h-9 w-24 animate-pulse rounded-full bg-white" />
            </div>
            <div className="space-y-4">
              <SkeletonCard />
              <div className="grid gap-3 md:grid-cols-2">
                <SkeletonCard compact />
                <SkeletonCard compact />
              </div>
            </div>
          </div>

          <div className="rounded-[32px] border border-slate-200/90 bg-white/78 p-5 shadow-[0_18px_44px_rgba(15,23,42,0.05)]">
            <div className="space-y-2">
              <div className="h-6 w-40 animate-pulse rounded-full bg-slate-200" />
              <SkeletonLine width="w-80" />
            </div>
            <div className="mt-4 grid gap-4">
              <div className="rounded-[24px] border border-slate-200 bg-white/80 p-4">
                <div className="flex items-start justify-between gap-3">
                  <div className="space-y-2">
                    <div className="h-3 w-24 animate-pulse rounded-full bg-slate-200" />
                    <div className="h-6 w-24 animate-pulse rounded-full bg-slate-200" />
                  </div>
                  <div className="h-9 w-28 animate-pulse rounded-full bg-white" />
                </div>
                <div className="mt-4 space-y-3">
                  <SkeletonCard compact />
                </div>
              </div>
              <div className="rounded-[24px] border border-slate-200 bg-white/80 p-4">
                <div className="flex items-start justify-between gap-3">
                  <div className="space-y-2">
                    <div className="h-3 w-28 animate-pulse rounded-full bg-slate-200" />
                    <div className="h-6 w-24 animate-pulse rounded-full bg-slate-200" />
                  </div>
                  <div className="h-9 w-20 animate-pulse rounded-full bg-white" />
                </div>
                <div className="mt-4 space-y-3">
                  <SkeletonCard compact />
                </div>
              </div>
            </div>
          </div>
        </section>

        <aside className="space-y-5">
          <div className="rounded-[28px] border border-slate-200/90 bg-white/85 p-5 shadow-[0_18px_44px_rgba(15,23,42,0.05)]">
            <div className="space-y-2">
              <div className="h-3 w-28 animate-pulse rounded-full bg-slate-200" />
              <div className="h-6 w-32 animate-pulse rounded-full bg-slate-200" />
            </div>
            <div className="mt-4 rounded-[24px] border border-slate-200 bg-white p-4">
              <SkeletonLine width="w-full" />
              <SkeletonLine width="w-1/2" />
              <div className="mt-4 h-2 w-full animate-pulse rounded-full bg-slate-200" />
            </div>
          </div>

          <div className="rounded-[28px] border border-slate-200/90 bg-white/85 p-5 shadow-[0_18px_44px_rgba(15,23,42,0.05)]">
            <div className="space-y-2">
              <div className="h-3 w-24 animate-pulse rounded-full bg-slate-200" />
              <div className="h-6 w-32 animate-pulse rounded-full bg-slate-200" />
            </div>
            <div className="mt-4 space-y-3">
              <div className="h-24 animate-pulse rounded-[24px] bg-slate-100" />
              <div className="h-24 animate-pulse rounded-[24px] bg-slate-100" />
            </div>
          </div>
        </aside>
      </div>
    </div>
  );
}
