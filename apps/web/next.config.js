import { env } from "node:process"

/** @type {import('next').NextConfig} */
const apiBaseUrl = (env.API_BASE_URL?.trim() || "http://localhost:8081").replace(/\/$/, "")

const nextConfig = {
  async rewrites() {
    return [{ source: "/backend/:path*", destination: `${apiBaseUrl}/:path*` }]
  },
}

export default nextConfig
