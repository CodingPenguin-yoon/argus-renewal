import { NextResponse } from "next/server";

import { getSearchIndex } from "@/krx/server/data-service";

export async function GET() {
  const payload = await getSearchIndex();
  return NextResponse.json(payload, {
    headers: {
      "Cache-Control": "public, max-age=60, s-maxage=300, stale-while-revalidate=300",
    },
  });
}
