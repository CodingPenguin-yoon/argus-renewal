import { redirect } from "next/navigation";

import { marketSignalSubtabHref } from "@/krx/market-signal/lib/subtabs";

export default async function KrxDerivativesPage() {
  redirect(marketSignalSubtabHref("derivatives"));
}
