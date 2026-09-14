/** @type {import('next').NextConfig} */
const nextConfig = {
  async rewrites() {
    return [
      {
        source: '/api/:path*',
        destination: `${process.env.NEXT_PUBLIC_API_BASE_URL || 'https://ai-powered-multiple-hospital-post-q5em.onrender.com'}/api/:path*`,
      },
    ];
  },
  // Enable proper handling for Vercel deployment
  output: 'standalone',
};

module.exports = nextConfig;