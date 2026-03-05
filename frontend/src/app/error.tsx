"use client";

import { ErrorState } from "@/components/ui/error-state";

export default function Error({ reset }: { error: Error & { digest?: string }; reset: () => void }) {
  return (
    <div className="mx-auto w-full max-w-6xl px-4 py-6">
      <ErrorState title="페이지를 불러오지 못했습니다" description="다시 시도해 주세요." />
      <button
        type="button"
        onClick={reset}
        className="mt-4 rounded-lg bg-slate-900 px-4 py-2 text-sm font-medium text-white"
      >
        다시 시도
      </button>
    </div>
  );
}
