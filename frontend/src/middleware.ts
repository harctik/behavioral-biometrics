import { NextResponse } from 'next/server';
import type { NextRequest } from 'next/server';
import { jwtVerify } from 'jose';

const protectedRoutes = ['/dashboard', '/admin', '/calibration', '/challenge', '/compliance', '/explainability', '/architecture', '/demo'];

/**
 * Verify JWT signature using jose (Edge-runtime compatible).
 * Returns true only if the token is cryptographically valid.
 */
async function isValidJwt(token: string): Promise<boolean> {
  const secret = process.env.JWT_SECRET_KEY;
  if (!secret) {
    // No secret configured — cannot verify; fail closed
    return false;
  }
  try {
    const encodedSecret = new TextEncoder().encode(secret);
    await jwtVerify(token, encodedSecret);
    return true;
  } catch {
    // Signature invalid, expired, or malformed
    return false;
  }
}

export default async function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;
  
  // Protect frontend routes centrally
  if (protectedRoutes.some(route => pathname.startsWith(route))) {
    // Check for session cookie — set by the login-verify proxy after successful auth
    const hasSession = request.cookies.has('session_id');
    const hasAccessToken = request.cookies.has('access_token_cookie');
    const isAuthenticated = hasSession || hasAccessToken;

    if (!isAuthenticated && !pathname.startsWith('/login')) {
      const loginUrl = new URL('/login', request.url);
      loginUrl.searchParams.set('redirect', pathname);
      return NextResponse.redirect(loginUrl);
    }
  }

  // Pre-auth route: OTP requires short-lived pending_mfa flag
  if (pathname.startsWith('/otp')) {
    const hasPendingMfa = request.cookies.has('pending_mfa');
    if (!hasPendingMfa) {
      return NextResponse.redirect(new URL('/login', request.url));
    }
  }

  // Intercept API calls to forward the access token as Bearer
  if (pathname.startsWith('/api/') && !pathname.startsWith('/api/auth/')) {
    const accessToken = request.cookies.get('access_token_cookie')?.value;
    const requestHeaders = new Headers(request.headers);
    if (accessToken) {
      requestHeaders.set('Authorization', `Bearer ${accessToken}`);
    }
    return NextResponse.next({ request: { headers: requestHeaders } });
  }
  
  return NextResponse.next();
}

export const config = {
  matcher: ['/((?!_next/static|_next/image|favicon.ico).*)'],
};
