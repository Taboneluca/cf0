/** @type {import('next').NextConfig} */
const nextConfig = {
  eslint: {
    ignoreDuringBuilds: true,
  },
  typescript: {
    ignoreBuildErrors: true,
  },
  images: {
    unoptimized: true,
  },
  transpilePackages: ['lucide-react'],
  
  // Add rewrites for API calls to go to Railway backend
  async rewrites() {
    return [
      {
        source: '/api/:path*',
        destination: 'https://api.cf0.ai/:path*'  // Railway FastAPI (update if different)
      }
    ];
  }
}

export default nextConfig
