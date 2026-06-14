import { NextResponse } from 'next/server';
import { cookies } from 'next/headers';

/**
 * Proxy route for MFA verification.
 * Reads the HttpOnly access_token_cookie and forwards it as a Bearer token
 * to the Flask backend, solving the CSRF/auth header issue.
 */
export async function POST(request: Request) {
  try {
    const body = await request.json();
    const { session_id, otp } = body;

    const cookieStore = await cookies();
    const accessToken = cookieStore.get('access_token_cookie')?.value;

    if (!accessToken) {
      return NextResponse.json(
        { error: 'Session expired. Please sign in again.' },
        { status: 401 }
      );
    }

    const backendUrl = process.env.BACKEND_URL || 'http://127.0.0.1:5000';

    const res = await fetch(`${backendUrl}/api/v1/auth/mfa/verify`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${accessToken}`,
      },
      body: JSON.stringify({ session_id, otp }),
    });

    const data = await res.json();

    if (!res.ok) {
      const errorField = data.error || data.msg;
      const errorMsg =
        typeof errorField === 'object' && errorField !== null
          ? errorField.message || JSON.stringify(errorField)
          : errorField || 'OTP verification failed';
      return NextResponse.json({ error: errorMsg }, { status: res.status });
    }

    const newToken = data.data?.access_token;
    const response = NextResponse.json({ success: true }, { status: 200 });

    // Clear the pending_mfa flag since MFA succeeded
    response.cookies.delete('pending_mfa');

    if (newToken) {
      response.cookies.set({
        name: 'access_token_cookie',
        value: newToken,
        httpOnly: true,
        secure: process.env.NODE_ENV === 'production',
        sameSite: 'lax',
        path: '/',
        maxAge: 15 * 60, // Must match JWT TTL, not session TTL
      });

      // Re-generate CSRF token for the new JWT
      const setCookieHeader = res.headers.get('set-cookie');
      if (setCookieHeader) {
        const csrfMatch = setCookieHeader.match(/csrf_access_token=([^;]+)/);
        if (csrfMatch) {
          response.cookies.set({
            name: 'csrf_access_token',
            value: csrfMatch[1],
            httpOnly: false,
            secure: process.env.NODE_ENV === 'production',
            sameSite: 'lax',
            path: '/',
            maxAge: 8 * 3600,
          });
        }
      }
    }

    return response;
  } catch (err: unknown) {
    const errorMsg =
      err instanceof Error ? err.message : 'Internal server error';
    return NextResponse.json({ error: errorMsg }, { status: 500 });
  }
}
