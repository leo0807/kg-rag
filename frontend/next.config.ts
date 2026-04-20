import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "standalone",
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: "http://localhost:8000/api/:path*",
      },
      {
        source: "/uploads/:path*",
        destination: "http://localhost:8000/uploads/:path*",
      },
    ];
  },
  // 禁用代理缓冲
  experimental: {
    proxyTimeout: 600000,
    // 允许更大的上传体积，避免 /api/ingest 超过 10MB 被截断
    middlewareClientMaxBodySize: "200mb",
  },
};

export default nextConfig;
