import assert from "node:assert/strict";
import test from "node:test";
import { PHASE_DEVELOPMENT_SERVER, PHASE_PRODUCTION_BUILD } from "next/constants.js";

import { createNextConfig, normalizeCdnUrl } from "./next.config.js";

test("CDN 地址只接受 HTTP(S) 并移除末尾斜杠", () => {
  assert.equal(normalizeCdnUrl(" https://cdn.example.com/ "), "https://cdn.example.com");
  assert.equal(normalizeCdnUrl("javascript:alert(1)"), undefined);
  assert.equal(normalizeCdnUrl("https://cdn.example.com/?version=1"), undefined);
  assert.equal(normalizeCdnUrl("not-a-url"), undefined);
});

test("生产环境将静态资源和图片优化请求指向 CDN", () => {
  const config = createNextConfig(PHASE_PRODUCTION_BUILD, {
    CDN_URL: "https://cdn.example.com/",
  });
  assert.equal(config.assetPrefix, "https://cdn.example.com");
  assert.equal(config.images.path, "https://cdn.example.com/_next/image");
  assert.deepEqual(config.images.formats, ["image/avif", "image/webp"]);
});

test("开发环境保持同源资源路径", () => {
  const config = createNextConfig(PHASE_DEVELOPMENT_SERVER, {
    CDN_URL: "https://cdn.example.com",
  });
  assert.equal(config.assetPrefix, undefined);
  assert.equal(config.images.path, "/_next/image");
});

test("Webpack 仅为客户端异步模块增加 Ant Design 缓存组", () => {
  const config = createNextConfig(PHASE_PRODUCTION_BUILD, {});
  const webpackConfig = { optimization: { splitChunks: { cacheGroups: {} } } };
  const result = config.webpack(webpackConfig, { isServer: false });
  assert.equal(result.optimization.splitChunks.cacheGroups.antd.name, "vendor-antd");
  assert.equal(result.optimization.splitChunks.cacheGroups.antd.chunks, "async");
});
