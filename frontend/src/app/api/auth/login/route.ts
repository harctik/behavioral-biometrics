import { NextResponse } from 'next/server';

export async function POST(request: Request) {
  try {
    const body = await request.json();
    const { username, password, behavioral_data } = body;

    const backendUrl = process.env.BACKEND_URL || 'http://127.0.0.1:5000';
    
    // Support both username and email login
    const isEmail = username.includes('@');
    const loginPayload = isEmail 
      ? { username, email: username, password, behavioral_data }
      : { username, password, behavioral_data };
    
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

    const response = NextResponse.json({ success: true, session_id, username }, { status: 200 });

    // Set secure HTTP-only cookies
    response.cookies.set({
      name: 'access_token_cookie',
      value: access_token,
      httpOnly: true,
      secure: process.env.NODE_ENV === 'production',
      sameSite: 'lax',
      path: '/',
      maxAge: 15 * 60, // 15 minutes (matches JWT expiry)
    });

    response.cookies.set({
      name: 'session_id',
      value: session_id,
      httpOnly: true,
      secure: process.env.NODE_ENV === 'production',
      sameSite: 'lax',
      path: '/',
      maxAge: 8 * 3600, // 8 hours (matches session expiry)
    });

    response.cookies.set({
      name: 'username',
      value: username,
      httpOnly: true,
      secure: process.env.NODE_ENV === 'production',
      sameSite: 'lax',
      path: '/',
      maxAge: 8 * 3600,
    });

    // Proxy CSRF token from Flask (non-HttpOnly so client can read it)
    const setCookieHeader = res.headers.get('set-cookie');
    if (setCookieHeader) {
      const csrfMatch = setCookieHeader.match(/csrf_access_token=([^;]+)/);
      if (csrfMatch) {
        response.cookies.set({
          name: 'csrf_access_token',
          value: csrfMatch[1],
          httpOnly: false, // Must be readable by apiClient.ts
          secure: process.env.NODE_ENV === 'production',
          sameSite: 'lax',
          path: '/',
          maxAge: 15 * 60,
        });
      }
    }

    let deviceId = request.headers.get('cookie')?.match(/device_id=([^;]+)/)?.[1];
    if (!deviceId) {
      deviceId = crypto.randomUUID();
    }
    response.cookies.set({
      name: 'device_id',
      value: deviceId,
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
