import { NextResponse } from 'next/server';
import { getBackendUrl } from '@/lib/backend-url';

export async function POST(request: Request) {
  try {
    const body = await request.json();
    const { username, password, device_id } = body;

    const backendUrl = getBackendUrl();

    // Support both username and email login
    const isEmail = username.includes('@');
    const loginPayload = isEmail
      ? { username, email: username, password, device_id }
      : { username, password, device_id };

    // Phase 1: Validate credentials, get challenge token
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
      const errorCode = typeof errorField === 'object' ? errorField.code : undefined;
      return NextResponse.json({ error: errorMsg, code: errorCode }, { status: res.status });
    }

    // Phase 1 returns challenge data — no JWT yet
    const {
      challenge_token,
      typing_prompt,
      enrollment_phase,
      sessions_completed,
      sessions_required,
      username: resolvedUsername,
    } = data.data;

    // Resolve device_id cookie
    let resolvedDeviceId = device_id || request.headers.get('cookie')?.match(/device_id=([^;]+)/)?.[1];
    if (!resolvedDeviceId) {
      resolvedDeviceId = crypto.randomUUID();
    }

    const response = NextResponse.json(
      {
        success: true,
        phase: 'challenge',
        challenge_token,
        typing_prompt,
        enrollment_phase,
        sessions_completed,
        sessions_required,
        username: resolvedUsername,
      },
      { status: 200 }
    );

    // Set device_id cookie for Phase 2
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
