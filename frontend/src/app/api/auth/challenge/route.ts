import { NextResponse } from 'next/server';
import { cookies } from 'next/headers';

export async function POST(request: Request) {
  try {
    const body = await request.json();
    const { password, behavioral_data } = body;
    
    // Read the current username from cookies
    const cookieStore = await cookies();
    const username = cookieStore.get('username')?.value;
    
    if (!username) {
      return NextResponse.json({ error: 'Session expired. Please log in again.' }, { status: 401 });
    }

    const backendUrl = process.env.BACKEND_URL || 'http://127.0.0.1:5000';
    
    // We treat the challenge as a re-authentication (login)
    const res = await fetch(`${backendUrl}/api/v1/auth/login`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ username, password, behavioral_data }),
    });

    const data = await res.json();

    if (!res.ok) {
      const errorField = data.error || data.msg;
      const errorMsg = typeof errorField === 'object' && errorField !== null
        ? errorField.message || JSON.stringify(errorField)
        : errorField || 'Verification failed';
      return NextResponse.json({ error: errorMsg }, { status: res.status });
    }

    const { access_token, session_id } = data.data;

    const response = NextResponse.json({ success: true, session_id, username }, { status: 200 });

    // Refresh the tokens
    response.cookies.set({
      name: 'access_token_cookie',
      value: access_token,
      httpOnly: true,
      secure: process.env.NODE_ENV === 'production',
      sameSite: 'lax',
      path: '/',
      maxAge: 15 * 60,
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

    return response;
  } catch (err: unknown) {
    const errorMsg = err instanceof Error ? err.message : 'Internal server error';
    return NextResponse.json({ error: errorMsg }, { status: 500 });
  }
}
