"use client";

import { useEffect, useRef, useState } from "react";

import { NewsTabDashboard } from "@/krx/news/components/news-tab-dashboard";
import type { NewsTabKey } from "@/krx/news/lib/tabs";
import type { NewsTabData } from "@/krx/types/domain";

const NEWS_TAB_POLL_INTERVAL_MS = 60_000;
const NEWS_TAB_POLL_PATH = "/api/krx/news-tab";
const KR_TAB_PAGE_SIZE = 5;

async function fetchNewsTabData(): Promise<NewsTabData> {
  const response = await fetch(NEWS_TAB_POLL_PATH, {
    cache: "no-store",
  });
  if (!response.ok) {
    throw new Error(`News tab polling failed (${response.status})`);
  }
  return response.json() as Promise<NewsTabData>;
}

export function NewsTabLiveDashboard({
  initialData,
  activeTab,
}: Readonly<{
  initialData: NewsTabData;
  activeTab: NewsTabKey;
}>) {
  const [data, setData] = useState(initialData);
  const [krPage, setKrPage] = useState(0);
  const isFetchingRef = useRef(false);
  const krPageCount = Math.max(1, Math.ceil(data.krCards.length / KR_TAB_PAGE_SIZE));

  useEffect(() => {
    setData(initialData);
  }, [initialData]);

  useEffect(() => {
    setKrPage(0);
  }, [activeTab]);

  useEffect(() => {
    setKrPage((current) => Math.min(current, Math.max(krPageCount - 1, 0)));
  }, [krPageCount]);

  useEffect(() => {
    let isCancelled = false;

    const loadLatest = async () => {
      if (isFetchingRef.current || document.visibilityState === "hidden") {
        return;
      }

      isFetchingRef.current = true;
      try {
        const nextData = await fetchNewsTabData();
        if (!isCancelled) {
          setData(nextData);
        }
      } catch (error) {
        if (!isCancelled) {
          console.error(
            JSON.stringify(
              {
                scope: "krx_news_tab_poll",
                status: "failed",
                error: error instanceof Error ? error.message : String(error),
              },
              null,
              0,
            ),
          );
        }
      } finally {
        isFetchingRef.current = false;
      }
    };

    const intervalId = window.setInterval(() => {
      void loadLatest();
    }, NEWS_TAB_POLL_INTERVAL_MS);

    const handleVisibilityChange = () => {
      if (document.visibilityState === "visible") {
        void loadLatest();
      }
    };

    document.addEventListener("visibilitychange", handleVisibilityChange);

    return () => {
      isCancelled = true;
      window.clearInterval(intervalId);
      document.removeEventListener("visibilitychange", handleVisibilityChange);
    };
  }, []);

  return (
    <NewsTabDashboard
      {...data}
      activeTab={activeTab}
      krPage={krPage}
      krPageSize={KR_TAB_PAGE_SIZE}
      krPageCount={krPageCount}
      onKrPagePrevious={() => setKrPage((current) => Math.max(current - 1, 0))}
      onKrPageNext={() => setKrPage((current) => Math.min(current + 1, Math.max(krPageCount - 1, 0)))}
    />
  );
}
