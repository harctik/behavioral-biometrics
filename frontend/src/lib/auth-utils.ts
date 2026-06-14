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
