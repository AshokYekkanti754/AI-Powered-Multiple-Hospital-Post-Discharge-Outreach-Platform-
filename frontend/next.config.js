/** @type {import('next').NextConfig} */
const nextConfig = {
  async rewrites() {
    return [
      {
        source: '/api/:path*',
        destination: `${process.env.NEXT_PUBLIC_API_BASE_URL || 'http://127.0.0.1:8000'}/api/:path*`,
      },
    ];
  },
  // Enable proper handling for Vercel deployment
  output: 'standalone',
};

module.exports = nextConfig;