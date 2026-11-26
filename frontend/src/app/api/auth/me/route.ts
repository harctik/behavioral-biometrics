import { NextResponse } from 'next/server';
import { cookies } from 'next/headers';
import { getBackendUrl } from '@/lib/backend-url';

/**
 * Server-side API route that reads HttpOnly cookies and returns
 * the current user's identity. This replaces localStorage.getItem("username")
 * with a secure, XSS-proof mechanism.
 *
 * The backend is asked first, because the login response does not always
 * carry a username for the cookie. The cookie is the fallback once the
 * short-lived access token has expired.
 */
export async function GET() {
  const cookieStore = await cookies();
  const token = cookieStore.get('access_token_cookie')?.value;
  const sessionId = cookieStore.get('session_id')?.value;

  if (token) {
    try {
      const res = await fetch(`${getBackendUrl()}/api/v1/auth/me`, {
        headers: { Authorization: `Bearer ${token}` },
        cache: 'no-store',
      });
      if (res.ok) {
        const body = await res.json();
        const user = body.data ?? body;
        return NextResponse.json({ ...user, session_id: sessionId, authenticated: true });
      }
    } catch {
      // Backend unreachable; fall back to the cookie below.
    }
  }

  const username = cookieStore.get('username')?.value;
  if (!username || !sessionId) {
    return NextResponse.json({ error: 'Not authenticated' }, { status: 401 });
  }

  return NextResponse.json({
    username,
    session_id: sessionId,
    authenticated: true,
  });
}
