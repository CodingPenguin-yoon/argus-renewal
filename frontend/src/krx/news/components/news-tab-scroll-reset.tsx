"use client";

import { useEffect } from "react";

export function NewsTabScrollReset() {
  useEffect(() => {
    const previousScrollRestoration = window.history.scrollRestoration;
    window.history.scrollRestoration = "manual";
    try {
      window.scrollTo({ top: 0, left: 0, behavior: "auto" });
    } catch {
      // jsdom does not implement scrollTo; browsers do.
    }

    return () => {
      window.history.scrollRestoration = previousScrollRestoration;
    };
  }, []);

  return null;
}
