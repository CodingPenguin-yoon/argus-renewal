import { DISCLAIMER_TEXT } from "@/krx/lib/constants";

export function DisclaimerBanner() {
  return (
    <aside
      aria-label="투자 유의 안내"
      className="rounded-2xl border border-amber-200/30 bg-gradient-to-r from-slate-900/92 to-slate-800/92 px-4 py-3 text-sm text-amber-100/95 shadow-sm"
    >
      <strong className="font-semibold">투자 유의:</strong> {DISCLAIMER_TEXT}
    </aside>
  );
}
