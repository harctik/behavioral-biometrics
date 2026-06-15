/**
 * Resolve the backend API base URL.
 * 
 * Priority:
 *   1. BACKEND_URL environment variable (server-side only)
 *   2. NEXT_PUBLIC_API_URL environment variable (available to client too)
 *   3. Development fallback: http://127.0.0.1:5000
 *   
 * In production, BACKEND_URL or NEXT_PUBLIC_API_URL MUST be set.
 * This is used by Next.js API route handlers (server-side only).
 */
export function getBackendUrl(): string {
  if (process.env.BACKEND_URL) {
    return process.env.BACKEND_URL;
  }
  if (process.env.NEXT_PUBLIC_API_URL) {
    return process.env.NEXT_PUBLIC_API_URL;
  }
  if (process.env.NODE_ENV === 'production') {
    console.warn(
      '[backend-url] WARNING: Neither BACKEND_URL nor NEXT_PUBLIC_API_URL is set in production. ' +
      'Set one of these environment variables to your backend URL.'
    );
  }
  // Development fallback
  return 'http://127.0.0.1:5000';
}
