function PulseBar({ width }: { width: string }) {
  return <div className={`h-3 animate-pulse rounded-full bg-slate-200 ${width}`} />;
}

function HeaderChip({ width }: { width: string }) {
  return <div className={`h-8 animate-pulse rounded-full bg-white/10 ${width}`} />;
}

export default function Loading() {
  return (
    <div className="market-shell market-shell-krx">
      <header className="sticky top-0 z-30 border-b border-amber-200/15 bg-slate-900/82 text-slate-100 backdrop-blur-md">
        <div className="mx-auto flex w-full max-w-6xl flex-col gap-3 px-4 py-3 md:py-4">
          <div className="flex items-center justify-between gap-3">
            <div className="h-7 w-28 animate-pulse rounded-full bg-white/12" />
            <div className="flex items-center gap-2">
              <HeaderChip width="w-28" />
              <HeaderChip width="w-20" />
            </div>
          </div>
          <div className="h-11 animate-pulse rounded-2xl border border-amber-200/25 bg-slate-800/45" />
          <div className="flex gap-2">
            <HeaderChip width="w-20" />
            <HeaderChip width="w-24" />
            <HeaderChip width="w-24" />
          </div>
        </div>
      </header>

      <div className="mx-auto flex w-full max-w-6xl flex-col gap-6 px-4 pt-6 md:pt-8">
        <section className="overflow-hidden rounded-[28px] border border-amber-200/18 bg-gradient-to-br from-slate-950 via-slate-900 to-stone-900 p-6 shadow-xl">
          <div className="space-y-3">
            <div className="h-3 w-44 animate-pulse rounded-full bg-white/15" />
            <div className="h-10 w-56 animate-pulse rounded-full bg-white/12" />
            <div className="space-y-2">
              <div className="h-3 w-full animate-pulse rounded-full bg-white/10" />
              <div className="h-3 w-4/5 animate-pulse rounded-full bg-white/10" />
            </div>
          </div>
          <div className="mt-5 flex flex-wrap gap-2">
            <div className="h-8 w-24 animate-pulse rounded-full bg-white/10" />
            <div className="h-8 w-28 animate-pulse rounded-full bg-white/10" />
            <div className="h-8 w-36 animate-pulse rounded-full bg-white/10" />
          </div>
        </section>

        <section className="rounded-[32px] border border-slate-200/90 bg-white/75 p-5 shadow-[0_18px_44px_rgba(15,23,42,0.05)]">
          <div className="space-y-3">
            <PulseBar width="w-40" />
            <PulseBar width="w-3/5" />
          </div>
          <div className="mt-5 grid gap-4 md:grid-cols-2 xl:grid-cols-3">
            {Array.from({ length: 3 }, (_, index) => (
              <div
                key={index}
                className="rounded-[24px] border border-slate-200 bg-[linear-gradient(145deg,rgba(255,255,255,0.98),rgba(248,250,252,0.92))] p-4"
              >
                <div className="flex gap-2">
                  <div className="h-6 w-16 animate-pulse rounded-full bg-slate-200" />
                  <div className="h-6 w-20 animate-pulse rounded-full bg-slate-100" />
                </div>
                <div className="mt-4 space-y-3">
                  <PulseBar width="w-full" />
                  <PulseBar width="w-4/5" />
                  <PulseBar width="w-3/5" />
                </div>
                <div className="mt-5 grid gap-3">
                  <div className="h-20 animate-pulse rounded-[18px] bg-slate-100" />
                  <div className="h-20 animate-pulse rounded-[18px] bg-slate-100" />
                </div>
              </div>
            ))}
          </div>
        </section>
      </div>
    </div>
  );
}
