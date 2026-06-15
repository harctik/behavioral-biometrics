/** @type {import('next').NextConfig} */
const nextConfig = {
  async headers() {
    const backendOrigin = process.env.NEXT_PUBLIC_API_URL || 'https://behavioral-biometrics-cp5l.onrender.com';
    return [
      {
        source: '/(.*)',
        headers: [
          { key: 'X-Frame-Options', value: 'DENY' },
          { key: 'X-Content-Type-Options', value: 'nosniff' },
          { key: 'Referrer-Policy', value: 'strict-origin-when-cross-origin' },
          { key: 'X-XSS-Protection', value: '1; mode=block' },
          {
            key: 'Cross-Origin-Opener-Policy',
            value: 'same-origin',
          },
          {
            // Allow accelerometer/gyroscope for behavioral biometrics gait detection
            key: 'Permissions-Policy',
            value: 'camera=(), microphone=(), geolocation=(), payment=(), accelerometer=(self), gyroscope=(self)',
          },
          {
            key: 'Strict-Transport-Security',
            value: 'max-age=31536000; includeSubDomains; preload',
          },
          {
            key: 'Content-Security-Policy',
            value: process.env.NODE_ENV === 'development'
              ? "default-src 'self'; script-src 'self' 'unsafe-inline' 'unsafe-eval'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; font-src 'self' data:; connect-src 'self' ws: http://127.0.0.1:5000 https://behavioral-biometrics-cp5l.onrender.com; frame-ancestors 'none';"
              : `default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; font-src 'self' data:; connect-src 'self' ${backendOrigin} https://*.onrender.com https://*.vercel.app; frame-ancestors 'none';`,
          },
        ],
      },
    ];
  },
  async rewrites() {
    const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'https://behavioral-biometrics-cp5l.onrender.com';
    return [
      {
        source: '/api/v1/:path*',
        destination: `${apiUrl}/api/v1/:path*`,
      },
      {
        // Frontend calls /api/auth/login → Backend is at /api/v1/auth/login
        source: '/api/auth/:path*',
        destination: `${apiUrl}/api/v1/auth/:path*`,
      },
      {
        source: '/static/:path*',
        destination: `${apiUrl}/static/:path*`,
      },
    ];
  },
};

export default nextConfig;

