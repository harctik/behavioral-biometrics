/**
 * Centralized cookie / token utilities.
 *
 * Eliminates the repeated `document.cookie.match(...)` pattern
 * spread across 6+ files and provides a single abstraction for
 * CSRF token and session ID retrieval.
 */

/** Read the CSRF access token from the cookie jar. */
export function getCsrfToken(): string {
  if (typeof document === "undefined") return "";
  return document.cookie.match(/csrf_access_token=([^;]+)/)?.[1] || "";
}

/** Read the session_id cookie. */
export function getSessionId(): string {
  if (typeof document === "undefined") return "";
  return document.cookie.match(/session_id=([^;]+)/)?.[1] || "";
}

/** Build common auth headers for backend API calls. */
export function authHeaders(): Record<string, string> {
  return {
    "Content-Type": "application/json",
    "X-CSRF-TOKEN": getCsrfToken(),
  };
}

/**
 * Enhanced fetch wrapper that:
 * 1. Auto-attaches X-CSRF-TOKEN header to all mutating requests
 * 2. Handles 429 rate limiting with retry + toast notification
 * 3. Handles 401 by redirecting to login
 */
export async function secureFetch(
  url: string,
  options: RequestInit = {},
  retries = 1
): Promise<Response> {
  const method = (options.method || "GET").toUpperCase();
  const headers = new Headers(options.headers);

  // Auto-attach CSRF for mutating methods
  if (["POST", "PUT", "DELETE", "PATCH"].includes(method) && !headers.has("X-CSRF-TOKEN")) {
    const csrf = getCsrfToken();
    if (csrf) headers.set("X-CSRF-TOKEN", csrf);
  }

  const res = await fetch(url, { ...options, headers });

  // Handle 429 Too Many Requests
  if (res.status === 429 && retries > 0) {
    const retryAfter = parseInt(res.headers.get("Retry-After") || "5", 10);
    const delay = Math.min(retryAfter * 1000, 30_000);
    // Dynamic import to avoid circular deps
    const { toast } = await import("sonner");
    toast.warning(`Rate limited. Retrying in ${retryAfter}s...`);
    await new Promise(r => setTimeout(r, delay));
    return secureFetch(url, options, retries - 1);
  }

  // Handle 401 Unauthorized — redirect to login
  if (res.status === 401 && typeof window !== "undefined" && !url.includes("/api/auth/")) {
    window.location.href = "/login";
  }

  return res;
}
