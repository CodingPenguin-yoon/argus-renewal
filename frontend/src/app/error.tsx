"use client";

export default function Error({ reset }: { error: Error & { digest?: string }; reset: () => void }) {
  return (
    <div className="mx-auto w-full max-w-6xl px-4 py-6">
      <div className="rounded-2xl border border-rose-200 bg-rose-50 p-6 text-center">
        <p className="text-base font-semibold text-rose-700">페이지를 불러오지 못했습니다</p>
        <p className="mt-1 text-sm text-rose-600">다시 시도해 주세요.</p>
      </div>
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
