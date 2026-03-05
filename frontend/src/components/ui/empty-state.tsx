export function EmptyState({ title, description }: { title: string; description: string }) {
  return (
    <div className="rounded-2xl border border-dashed border-slate-300 bg-slate-50 p-6 text-center">
      <p className="text-base font-medium text-slate-800">{title}</p>
      <p className="mt-1 text-sm text-slate-600">{description}</p>
    </div>
  );
}
