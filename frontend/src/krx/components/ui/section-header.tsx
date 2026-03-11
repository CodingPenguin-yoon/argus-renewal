export function SectionHeader({
  title,
  description,
  action,
}: {
  title: string;
  description?: string;
  action?: React.ReactNode;
}) {
  return (
    <div className="mb-4 flex items-start justify-between gap-3">
      <div>
        <h2 className="text-lg font-extrabold tracking-tight text-slate-900 md:text-xl">{title}</h2>
        {description ? <p className="mt-1 text-sm text-slate-600 md:text-[0.95rem]">{description}</p> : null}
      </div>
      {action}
    </div>
  );
}
