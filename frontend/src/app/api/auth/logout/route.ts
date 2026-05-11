import { NextResponse, NextRequest } from 'next/server';

export async function POST(request: NextRequest) {
  try {
    let session_id: string | undefined;
    try {
      const body = await request.json();
      session_id = body?.session_id;
    } catch {
      // Body is empty or not JSON, fallback to cookie
    }

    if (!session_id) {
      session_id = request.cookies.get('session_id')?.value;
    }

    const backendUrl = process.env.BACKEND_URL || 'http://127.0.0.1:5000';

    try {
      await fetch(`${backendUrl}/api/v1/auth/logout`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${request.cookies.get('access_token_cookie')?.value}`
        },
        body: JSON.stringify({ session_id }),
      });
    } catch {
      // Ignore backend errors for logout
    }

    const response = NextResponse.json({ success: true }, { status: 200 });

    response.cookies.delete('access_token_cookie');
    response.cookies.delete('session_id');
    response.cookies.delete('device_id');
    response.cookies.delete('csrf_access_token');

    return response;
  } catch (err: unknown) {
    const errorMsg = err instanceof Error ? err.message : 'Internal server error';
    return NextResponse.json({ error: errorMsg }, { status: 500 });
  }
}
