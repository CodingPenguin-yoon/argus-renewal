"use client";

type Option = { label: string; value: string };

export function FilterBar({
  options,
  value,
  onChange,
  ariaLabel,
}: {
  options: Option[];
  value: string;
  onChange: (next: string) => void;
  ariaLabel: string;
}) {
  return (
    <div className="flex gap-2 overflow-x-auto pb-2" role="tablist" aria-label={ariaLabel}>
      {options.map((option) => {
        const active = option.value === value;
        return (
          <button
            key={option.value}
            type="button"
            role="tab"
            aria-selected={active}
            onClick={() => onChange(option.value)}
            className={`rounded-full border px-3 py-1.5 text-sm whitespace-nowrap transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-amber-200 ${
              active
                ? "border-amber-200 bg-amber-200 text-slate-900 shadow-sm"
                : "border-slate-500/70 bg-slate-800/78 text-slate-100 hover:border-slate-400 hover:bg-slate-700/78"
            }`}
          >
            {option.label}
          </button>
        );
      })}
    </div>
  );
}
