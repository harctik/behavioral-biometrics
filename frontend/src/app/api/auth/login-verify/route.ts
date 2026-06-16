import { NextResponse } from 'next/server';
import { getBackendUrl } from '@/lib/backend-url';

export async function POST(request: Request) {
  try {
    const body = await request.json();
    const { challenge_token, typed_text, behavioral_data, keystroke_profile } = body;

    const backendUrl = getBackendUrl();

    // Phase 2: Send behavioral data for verification
    const res = await fetch(`${backendUrl}/api/v1/auth/login/verify`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-Device-Id': request.headers.get('cookie')?.match(/device_id=([^;]+)/)?.[1] || '',
      },
      body: JSON.stringify({
        challenge_token,
        typed_text,
        behavioral_data,
        keystroke_profile,
      }),
    });

    const data = await res.json();

    if (!res.ok) {
      const errorField = data.error || data.msg;
      const errorMsg = typeof errorField === 'object' && errorField !== null
        ? errorField.message || JSON.stringify(errorField)
        : errorField || 'Verification failed';
      const errorCode = typeof errorField === 'object' ? errorField.code : undefined;
      // Never forward 403 (behavioral block) — blocking is handled client-side by accuracy check
      const safeStatus = res.status === 403 ? 401 : res.status;
      return NextResponse.json({ error: errorMsg, code: errorCode }, { status: safeStatus });
    }

    const {
      access_token,
      session_id,
      mfa_required,
      decision,
      match_score,
      device_new,
      enrollment,
    } = data.data;

    const response = NextResponse.json(
      {
        success: true,
        session_id,
        mfa_required,
        decision,
        match_score,
        device_new,
        enrollment,
      },
      { status: 200 }
    );

    // Set secure HTTP-only cookies — maxAge matches JWT TTL
    const jwtMaxAge = 15 * 60; // 15 minutes

    response.cookies.set({
      name: 'access_token_cookie',
      value: access_token,
      httpOnly: true,
      secure: process.env.NODE_ENV === 'production',
      sameSite: 'lax',
      path: '/',
      maxAge: jwtMaxAge,
    });

    response.cookies.set({
      name: 'session_id',
      value: session_id,
      httpOnly: false,
      secure: process.env.NODE_ENV === 'production',
      sameSite: 'lax',
      path: '/',
      maxAge: 8 * 3600,
    });

    if (mfa_required) {
      response.cookies.set({
        name: 'pending_mfa',
        value: 'true',
        httpOnly: true,
        secure: process.env.NODE_ENV === 'production',
        sameSite: 'lax',
        path: '/',
        maxAge: 5 * 60,
      });
    }

    response.cookies.set({
      name: 'username',
      value: data.data?.username || '',
      httpOnly: true,
      secure: process.env.NODE_ENV === 'production',
      sameSite: 'lax',
      path: '/',
      maxAge: 8 * 3600,
    });

    // Proxy CSRF token from Flask
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
          maxAge: jwtMaxAge,
        });
      }
    }

    return response;
  } catch (err: unknown) {
    const errorMsg = err instanceof Error ? err.message : 'Internal server error';
    return NextResponse.json({ error: errorMsg }, { status: 500 });
  }
}
