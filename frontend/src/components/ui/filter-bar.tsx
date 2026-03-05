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
            className={`rounded-full border px-3 py-1.5 text-sm whitespace-nowrap transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sky-500 ${
              active
                ? "border-sky-600 bg-sky-600 text-white"
                : "border-slate-300 bg-white text-slate-700 hover:border-slate-400"
            }`}
          >
            {option.label}
          </button>
        );
      })}
    </div>
  );
}
