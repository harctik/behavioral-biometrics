"use client";

import { useEffect } from "react";

export function ServiceWorkerRegistration() {
  useEffect(() => {
    if (!("serviceWorker" in navigator)) {
      return;
    }

    navigator.serviceWorker.register("/service-worker.js").catch(() => {
      // Keep failures silent in client UI.
    });
  }, []);

  return null;
}
