/**
 * Central API client for all backend communication.
 *
 * CSRF tokens are now read directly from the non-HttpOnly
 * csrf_access_token cookie set by Flask-JWT-Extended.
 * LocalStorage is no longer used for session or security tokens.
 */

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

  const response = await fetch(`/api${endpoint}`, {
    ...options,
    headers,
  });

  const data = await response.json();

  if (!response.ok) {
    const errorField = data.error || data.msg;
    const errorMsg = typeof errorField === "object" && errorField !== null 
      ? errorField.message || JSON.stringify(errorField)
      : errorField;
    throw new Error(errorMsg || "An API error occurred");
  }

  return data;
}
