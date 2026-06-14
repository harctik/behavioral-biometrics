/**
 * Central API client for all backend communication.
 *
 * Features:
 * - Automatic CSRF token injection from cookie
 * - Silent JWT refresh on 401 responses (prevents session expiry)
 * - Retry-once pattern for seamless token renewal
 */

let isRefreshing = false;
let refreshPromise: Promise<boolean> | null = null;

/** Attempt to silently refresh the access token. */
async function silentRefresh(): Promise<boolean> {
  try {
    const res = await fetch("/api/v1/auth/refresh", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      credentials: "include",
    });
    if (res.ok) {
      return true;
    }
    return false;
  } catch {
    return false;
  }
}

/** Get or share a single in-flight refresh attempt. */
function getRefreshPromise(): Promise<boolean> {
  if (!refreshPromise) {
    isRefreshing = true;
    refreshPromise = silentRefresh().finally(() => {
      isRefreshing = false;
      refreshPromise = null;
    });
  }
  return refreshPromise;
}

export async function apiClient<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
  const headers = new Headers(options.headers);
  
  if (typeof window !== "undefined") {
    // Read Flask-JWT-Extended CSRF token from cookie
    const match = document.cookie.match(/csrf_access_token=([^;]+)/);
    if (match && match[1] && !headers.has("X-CSRF-TOKEN")) {
      headers.set("X-CSRF-TOKEN", match[1]);
    }
  }
  
  if (!headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }

  const doFetch = () => fetch(`/api${endpoint}`, {
    ...options,
    headers,
    credentials: "include",
  });

  let response = await doFetch();

  // On 401, attempt silent refresh and retry once
  if (response.status === 401 && typeof window !== "undefined") {
    const refreshed = await getRefreshPromise();
    if (refreshed) {
      // Re-read CSRF token after refresh (cookie may have changed)
      const newMatch = document.cookie.match(/csrf_access_token=([^;]+)/);
      if (newMatch && newMatch[1]) {
        headers.set("X-CSRF-TOKEN", newMatch[1]);
      }
      response = await doFetch();
    }
  }

  const data = await response.json();

  if (!response.ok) {
    // If still 401 after refresh, redirect to login
    if (response.status === 401 && typeof window !== "undefined") {
      window.location.href = "/login";
      throw new Error("Session expired");
    }
    
    const errorField = data.error || data.msg;
    const errorMsg = typeof errorField === "object" && errorField !== null 
      ? errorField.message || JSON.stringify(errorField)
      : errorField;
    throw new Error(errorMsg || "An API error occurred");
  }

  return data;
}
