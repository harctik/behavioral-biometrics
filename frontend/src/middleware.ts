import { NextResponse } from 'next/server';
import type { NextRequest } from 'next/server';

export default function middleware(request: NextRequest) {
  // We only want to intercept API calls that are being rewritten to the backend
  if (request.nextUrl.pathname.startsWith('/api/') && 
      !request.nextUrl.pathname.startsWith('/api/auth/')) {
    
    // Get the tokens from cookies
    const accessToken = request.cookies.get('access_token')?.value;
    
    // Create new headers object
    const requestHeaders = new Headers(request.headers);
    
    // Append the Bearer token if it exists
    if (accessToken) {
      requestHeaders.set('Authorization', `Bearer ${accessToken}`);
    }
    
    // Return the response with mutated headers
    return NextResponse.next({
      request: {
        headers: requestHeaders,
      },
    });
  }
  
  return NextResponse.next();
}

export const config = {
  matcher: '/api/:path*',
};
