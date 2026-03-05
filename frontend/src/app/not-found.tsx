import Link from "next/link";

export default function NotFoundPage() {
  return (
    <div className="mx-auto flex min-h-[50vh] w-full max-w-6xl flex-col items-center justify-center gap-3 px-4 py-8 text-center">
      <h1 className="text-2xl font-bold text-slate-900">페이지를 찾을 수 없습니다</h1>
      <p className="text-slate-600">입력한 주소가 올바른지 확인해 주세요.</p>
      <Link href="/" className="rounded-lg bg-slate-900 px-4 py-2 text-sm font-medium text-white">
        홈으로 이동
      </Link>
    </div>
  );
}
