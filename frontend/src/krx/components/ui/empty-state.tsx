export function EmptyState({ title, description }: { title: string; description: string }) {
  return (
    <div className="rounded-2xl border border-dashed border-slate-500/70 bg-slate-800/90 p-6 text-center">
      <p className="text-base font-medium text-slate-100">{title}</p>
      <p className="mt-1 text-sm text-slate-300/90">{description}</p>
    </div>
  );
}
