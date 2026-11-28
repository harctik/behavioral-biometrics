"use client";

import { useCallback, useEffect, useState, useSyncExternalStore } from "react";

const noopSubscribe = () => () => {};

/** False during server render and hydration, true afterwards. */
export function useIsClient() {
  return useSyncExternalStore(noopSubscribe, () => true, () => false);
}

const STORAGE_EVENT = "bba:storage";

function subscribeStorage(onChange: () => void) {
  window.addEventListener("storage", onChange);
  window.addEventListener(STORAGE_EVENT, onChange);
  return () => {
    window.removeEventListener("storage", onChange);
    window.removeEventListener(STORAGE_EVENT, onChange);
  };
}

export function readStorage(key: string) {
  try {
    return window.localStorage.getItem(key);
  } catch {
    return null;
  }
}

/** A localStorage string that is safe to read during render. */
export function useStoredString(key: string): [string | null, (value: string) => void] {
  const value = useSyncExternalStore(subscribeStorage, () => readStorage(key), () => null);
  const setValue = useCallback(
    (next: string) => {
      try {
        window.localStorage.setItem(key, next);
      } catch {
        return;
      }
      window.dispatchEvent(new Event(STORAGE_EVENT));
    },
    [key],
  );
  return [value, setValue];
}

/** The current time, refreshed on an interval, so render stays pure. */
export function useNow(intervalMs = 60_000) {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const id = setInterval(() => setNow(Date.now()), intervalMs);
    return () => clearInterval(id);
  }, [intervalMs]);
  return now;
}
