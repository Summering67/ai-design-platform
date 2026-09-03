import { env } from "node:process";
import { PHASE_DEVELOPMENT_SERVER } from "next/constants.js";

/** @type {import('next').NextConfig} */
const apiBaseUrl = (env.API_BASE_URL?.trim() || "http://localhost:8081").replace(/\/$/, "");

export const normalizeCdnUrl = (value) => {
  if (!value?.trim()) return undefined;
  try {
    const url = new URL(value.trim());
    if (
      (url.protocol !== "https:" && url.protocol !== "http:") ||
      url.username ||
      url.password ||
      url.search ||
      url.hash
    )
      return undefined;
    return `${url.origin}${url.pathname.replace(/\/+$/, "")}`;
  } catch {
    return undefined;
  }
};

const addClientCacheGroups = (config, isServer) => {
  if (
    isServer ||
    !config.optimization?.splitChunks ||
    typeof config.optimization.splitChunks !== "object"
  )
    return config;
  const cacheGroups = config.optimization.splitChunks.cacheGroups;
  if (!cacheGroups || typeof cacheGroups !== "object") return config;
  cacheGroups.antd = {
    test: /[\\/]node_modules[\\/](?:\.pnpm[\\/].+[\\/]node_modules[\\/])?(?:antd|@ant-design)[\\/]/,
    name: "vendor-antd",
    chunks: "async",
    priority: 30,
    reuseExistingChunk: true,
  };
  return config;
};

export const createNextConfig = (phase, runtimeEnv = env) => {
  const cdnUrl = normalizeCdnUrl(runtimeEnv.CDN_URL);
  const assetPrefix = phase === PHASE_DEVELOPMENT_SERVER ? undefined : cdnUrl;

  return {
    assetPrefix,
    crossOrigin: assetPrefix ? "anonymous" : undefined,
    images: {
      formats: ["image/avif", "image/webp"],
      minimumCacheTTL: 86400,
      path: assetPrefix ? `${assetPrefix}/_next/image` : "/_next/image",
      qualities: [60, 75, 85],
    },
    experimental: {
      optimizePackageImports: ["antd", "lucide-react"],
    },
    async rewrites() {
      return [{ source: "/backend/:path*", destination: `${apiBaseUrl}/:path*` }];
    },
    webpack(config, { isServer }) {
      return addClientCacheGroups(config, isServer);
    },
  };
};

export default createNextConfig;
