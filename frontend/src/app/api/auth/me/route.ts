import { NextResponse } from 'next/server';
import { cookies } from 'next/headers';

/**
 * Server-side API route that reads HttpOnly cookies and returns
 * the current user's identity. This replaces localStorage.getItem("username")
 * with a secure, XSS-proof mechanism.
 */
export async function GET() {
  const cookieStore = await cookies();
  const username = cookieStore.get('username')?.value;
  const sessionId = cookieStore.get('session_id')?.value;

  if (!username || !sessionId) {
    return NextResponse.json({ error: 'Not authenticated' }, { status: 401 });
  }

  return NextResponse.json({
    username,
    session_id: sessionId,
    authenticated: true,
  });
}
