export function LoadingState({ label = "데이터를 불러오는 중입니다..." }: { label?: string }) {
  return (
    <div className="rounded-2xl border border-slate-200 bg-white p-6">
      <div className="h-3 w-2/5 animate-pulse rounded bg-slate-200" />
      <div className="mt-3 h-3 w-4/5 animate-pulse rounded bg-slate-200" />
      <p className="mt-4 text-sm text-slate-500">{label}</p>
    </div>
  );
}
