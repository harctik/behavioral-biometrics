import { NextResponse } from 'next/server';
import { cookies } from 'next/headers';
import { getBackendUrl } from '@/lib/backend-url';

export async function POST(request: Request) {
  try {
    const body = await request.json();
    const { password, behavioral_data } = body;
    
    // Read the current username from cookies
    const cookieStore = await cookies();
    const sessionId = cookieStore.get('session_id')?.value;
    const accessToken = cookieStore.get('access_token_cookie')?.value;
    
    if (!sessionId || !accessToken) {
      return NextResponse.json({ error: 'Session expired. Please log in again.' }, { status: 401 });
    }

    const backendUrl = getBackendUrl();
    
    // We treat the challenge as a step-up authentication within the SAME session
    const res = await fetch(`${backendUrl}/api/v1/auth/password-verify`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${accessToken}`,
      },
      body: JSON.stringify({ password, behavioral_data }),
    });

    const data = await res.json();

    if (!res.ok) {
      const errorField = data.error || data.msg;
      const errorMsg = typeof errorField === 'object' && errorField !== null
        ? errorField.message || JSON.stringify(errorField)
        : errorField || 'Verification failed';
      return NextResponse.json({ error: errorMsg }, { status: res.status });
    }

    return NextResponse.json({ success: true, session_id: sessionId }, { status: 200 });
  } catch (err: unknown) {
    const errorMsg = err instanceof Error ? err.message : 'Internal server error';
    return NextResponse.json({ error: errorMsg }, { status: 500 });
  }
}
