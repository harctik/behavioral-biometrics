/** @type {import('next').NextConfig} */
const nextConfig = {
  async rewrites() {
    const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:5000';
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
