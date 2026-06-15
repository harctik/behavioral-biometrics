/**
 * Resolve the backend API base URL.
 * 
 * In development: uses BACKEND_URL env var (defaults to localhost:5000)
 * In production: uses BACKEND_URL env var (defaults to Render deployment)
 * 
 * This is used by Next.js API route handlers (server-side only).
 */
export function getBackendUrl(): string {
  if (process.env.BACKEND_URL) {
    return process.env.BACKEND_URL;
  }
  // Production fallback — the live Render backend
  if (process.env.NODE_ENV === 'production') {
    return 'https://behavioral-biometrics-cp5l.onrender.com';
  }
  // Development fallback
  return 'http://127.0.0.1:5000';
}
