import { DISCLAIMER_TEXT } from "@/lib/constants";

export function DisclaimerBanner() {
  return (
    <aside
      aria-label="투자 유의 안내"
      className="rounded-xl border border-amber-300 bg-amber-50 px-4 py-3 text-sm text-amber-900"
    >
      <strong className="font-semibold">투자 유의:</strong> {DISCLAIMER_TEXT}
    </aside>
  );
}
