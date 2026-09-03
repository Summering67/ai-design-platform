# Web 应用

主站使用 Next.js App Router，并通过 Webpack 对生产资源进行分包。

## CDN 与图片优化

生产构建可设置 `CDN_URL`（例如 `https://cdn.example.com`）。构建产物中的 JavaScript、CSS、字体等 `/_next/static/` 资源会改由该域名加载，Next.js 图片优化请求也会指向 CDN 的 `/_next/image`。

CDN 需要将 `/_next/static/` 映射到当前构建的 `.next/static/`，并把 `/_next/image` 回源到 Web 服务；图片回源规则必须透传浏览器的 `Accept` 请求头。不要将 `.next` 中的服务端文件公开到 CDN。

图片默认生成 AVIF/WebP，允许质量档位为 60、75、85，优化结果至少缓存 24 小时。页面图片应使用 `next/image`，并按实际展示宽度提供 `sizes`，避免客户端下载过大资源。

## Getting Started

First, run the development server:

```bash
npm run dev
# or
yarn dev
# or
pnpm dev
# or
bun dev
```

Open [http://localhost:3000](http://localhost:3000) with your browser to see the result.

You can start editing the page by modifying `app/page.tsx`. The page auto-updates as you edit the file.

This project uses [`next/font`](https://nextjs.org/docs/app/building-your-application/optimizing/fonts) to automatically optimize and load Inter, a custom Google Font.

## Learn More

To learn more about Next.js, take a look at the following resources:

- [Next.js Documentation](https://nextjs.org/docs) - learn about Next.js features and API.
- [Learn Next.js](https://nextjs.org/learn) - an interactive Next.js tutorial.

You can check out [the Next.js GitHub repository](https://github.com/vercel/next.js) - your feedback and contributions are welcome!

## Deploy on Vercel

The easiest way to deploy your Next.js app is to use the [Vercel Platform](https://vercel.com/new?utm_medium=default-template&filter=next.js&utm_source=create-next-app&utm_campaign=create-next-app-readme) from the creators of Next.js.

Check out our [Next.js deployment documentation](https://nextjs.org/docs/app/building-your-application/deploying) for more details.
