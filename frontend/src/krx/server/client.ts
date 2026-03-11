import { env } from "@/krx/lib/env";

export type ApiListResponse<T> = { items: T[] };
export type ApiItemResponse<T> = { item: T };

const API_PREFIX = "/api/krx";
const BACKEND_BASE_URL = env.BACKEND_BASE_URL.replace(/\/+$/, "");

export async function getKrxJson<T>(path: string): Promise<T> {
  const response = await fetch(`${BACKEND_BASE_URL}${API_PREFIX}${path}`, {
    cache: "no-store",
  });

  if (!response.ok) {
    throw new Error(`KRX request failed: ${path} (${response.status})`);
  }

  return response.json() as Promise<T>;
}

export async function getKrxJsonOrNull<T>(path: string): Promise<T | null> {
  const response = await fetch(`${BACKEND_BASE_URL}${API_PREFIX}${path}`, {
    cache: "no-store",
  });

  if (response.status === 404) {
    return null;
  }

  if (!response.ok) {
    throw new Error(`KRX request failed: ${path} (${response.status})`);
  }

  return response.json() as Promise<T>;
}
