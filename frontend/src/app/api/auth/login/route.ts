import { NextResponse } from 'next/server';

export async function POST(request: Request) {
  try {
    const body = await request.json();
    const { username, password, behavioral_data, device_id, trust_device } = body;

    const backendUrl = process.env.BACKEND_URL || 'http://127.0.0.1:5000';
    
    // Support both username and email login
    const isEmail = username.includes('@');
    const loginPayload = isEmail 
      ? { username, email: username, password, behavioral_data, device_id, trust_device }
      : { username, password, behavioral_data, device_id, trust_device };
    
    // Call the Flask API
    const res = await fetch(`${backendUrl}/api/v1/auth/login`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(loginPayload),
    });

    const data = await res.json();

    if (!res.ok) {
      const errorField = data.error || data.msg;
      const errorMsg = typeof errorField === 'object' && errorField !== null
        ? errorField.message || JSON.stringify(errorField)
        : errorField || 'Login failed';
      return NextResponse.json({ error: errorMsg }, { status: res.status });
    }

    const { access_token, session_id } = data.data;
    const mfaRequired = data.data?.mfa_required || data.mfa_required || false;

    // Forward mfa_required to the client so the login page can route to /otp
    const response = NextResponse.json(
      { success: true, session_id, username, mfa_required: mfaRequired },
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
      httpOnly: true,
      secure: process.env.NODE_ENV === 'production',
      sameSite: 'lax',
      path: '/',
      maxAge: 8 * 3600,
    });

    if (mfaRequired) {
      response.cookies.set({
        name: 'pending_mfa',
        value: 'true',
        httpOnly: true,
        secure: process.env.NODE_ENV === 'production',
        sameSite: 'lax',
        path: '/',
        maxAge: 5 * 60, // 5 minutes short-lived flag
      });
    }

    // Username stored HttpOnly — clients should use /api/auth/me instead
    response.cookies.set({
      name: 'username',
      value: username,
      httpOnly: true,
      secure: process.env.NODE_ENV === 'production',
      sameSite: 'lax',
      path: '/',
      maxAge: 8 * 3600,
    });

    // Proxy CSRF token from Flask (non-HttpOnly so SPA can read it)
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

    let resolvedDeviceId = device_id || request.headers.get('cookie')?.match(/device_id=([^;]+)/)?.[1];
    if (!resolvedDeviceId) {
      resolvedDeviceId = crypto.randomUUID();
    }
    response.cookies.set({
      name: 'device_id',
      value: resolvedDeviceId,
      httpOnly: true,
      secure: process.env.NODE_ENV === 'production',
      sameSite: 'lax',
      path: '/',
      maxAge: 365 * 24 * 3600,
    });

    return response;
  } catch (err: unknown) {
    const errorMsg = err instanceof Error ? err.message : 'Internal server error';
    return NextResponse.json({ error: errorMsg }, { status: 500 });
  }
}
