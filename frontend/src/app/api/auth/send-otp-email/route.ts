import { NextResponse } from 'next/server';
import { cookies } from 'next/headers';
import { getBackendUrl } from '@/lib/backend-url';

export async function POST(request: Request) {
  try {
    const body = await request.json();
    const { session_id } = body;

    const cookieStore = await cookies();
    const accessToken = cookieStore.get('access_token_cookie')?.value;

    if (!accessToken) {
      return NextResponse.json(
        { error: 'Session expired. Please sign in again.' },
        { status: 401 }
      );
    }

    const backendUrl = getBackendUrl();

    const res = await fetch(`${backendUrl}/api/v1/auth/send-otp-email`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${accessToken}`,
      },
      body: JSON.stringify({ session_id }),
    });

    const data = await res.json();

    if (!res.ok) {
      return NextResponse.json(
        { error: data.error || data.msg || 'Failed to send OTP' },
        { status: res.status }
      );
    }

    return NextResponse.json(data, { status: 200 });
  } catch (err: unknown) {
    return NextResponse.json(
      { error: err instanceof Error ? err.message : 'Internal server error' },
      { status: 500 }
    );
  }
}
