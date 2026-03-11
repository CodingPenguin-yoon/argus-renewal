import { cva } from "class-variance-authority";

import { cn } from "@/krx/lib/utils";

const badgeVariants = cva(
  "inline-flex items-center rounded-full px-2.5 py-1 text-xs font-medium ring-1 ring-inset",
  {
    variants: {
      variant: {
        default: "bg-slate-100 text-slate-700 ring-slate-200",
        positive: "bg-emerald-50 text-emerald-700 ring-emerald-200",
        neutral: "bg-blue-50 text-blue-700 ring-blue-200",
        negative: "bg-rose-50 text-rose-700 ring-rose-200",
        high: "bg-amber-50 text-amber-800 ring-amber-300",
        medium: "bg-blue-50 text-blue-700 ring-blue-200",
        low: "bg-zinc-100 text-zinc-700 ring-zinc-200",
      },
    },
    defaultVariants: {
      variant: "default",
    },
  },
);

export function Badge({ className, variant, children }: React.PropsWithChildren<{ className?: string; variant?: "default" | "positive" | "neutral" | "negative" | "high" | "medium" | "low" }>) {
  return <span className={cn(badgeVariants({ variant }), className)}>{children}</span>;
}
