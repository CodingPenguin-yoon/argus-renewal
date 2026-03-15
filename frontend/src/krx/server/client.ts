import { env } from "@/krx/lib/env";

export type ApiListResponse<T> = { items: T[] };
export type ApiItemResponse<T> = { item: T };
export type KrxFetchOptions = {
  revalidate?: number;
  cache?: RequestCache;
};

const API_PREFIX = "/api/krx";
const BACKEND_BASE_URL = env.BACKEND_BASE_URL.replace(/\/+$/, "");
export const KRX_SHORT_REVALIDATE_SECONDS = 30;

function buildKrxFetchOptions(options?: KrxFetchOptions) {
  if (typeof options?.revalidate === "number") {
    return { next: { revalidate: options.revalidate } };
  }

  return { cache: options?.cache ?? "no-store" };
}

export async function getKrxJson<T>(path: string, options?: KrxFetchOptions): Promise<T> {
  const response = await fetch(`${BACKEND_BASE_URL}${API_PREFIX}${path}`, buildKrxFetchOptions(options));

  if (!response.ok) {
    throw new Error(`KRX request failed: ${path} (${response.status})`);
  }

  return response.json() as Promise<T>;
}

export async function getKrxJsonOrNull<T>(path: string, options?: KrxFetchOptions): Promise<T | null> {
  const response = await fetch(`${BACKEND_BASE_URL}${API_PREFIX}${path}`, buildKrxFetchOptions(options));

  if (response.status === 404) {
    return null;
  }

  if (!response.ok) {
    throw new Error(`KRX request failed: ${path} (${response.status})`);
  }

  return response.json() as Promise<T>;
}
