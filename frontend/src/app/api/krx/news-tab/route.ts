import { NextResponse } from "next/server";

import { getNewsTabData } from "@/krx/server/data-service";

export const dynamic = "force-dynamic";

export async function GET() {
  const payload = await getNewsTabData();
  return NextResponse.json(payload, {
    headers: {
      "Cache-Control": "no-store, max-age=0",
    },
  });
}
