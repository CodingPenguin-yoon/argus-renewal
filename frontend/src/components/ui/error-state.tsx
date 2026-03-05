export function ErrorState({ title, description }: { title: string; description: string }) {
  return (
    <div className="rounded-2xl border border-rose-200 bg-rose-50 p-6 text-center">
      <p className="text-base font-semibold text-rose-700">{title}</p>
      <p className="mt-1 text-sm text-rose-600">{description}</p>
    </div>
  );
}
