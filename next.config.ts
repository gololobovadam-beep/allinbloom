import type { NextConfig } from 'next';

const apiBase = (process.env.API_BASE_URL || "http://localhost:8000").replace(/\/+$/, "");
// CI and local validation can use an isolated build directory without
// touching a running development server's .next cache.
const distDir = process.env.NEXT_DIST_DIR?.trim() || ".next";

const nextConfig: NextConfig = {
  output: "standalone",
  distDir,
  images: {
    unoptimized: true,
  },
  async rewrites() {
    return {
      beforeFiles: [
        {
          source: "/api/:path*",
          destination: `${apiBase}/api/:path*`,
        },
      ],
    };
  },
  async headers() {
    const securityHeaders = [
      { key: "X-Content-Type-Options", value: "nosniff" },
      { key: "X-Frame-Options", value: "DENY" },
      { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
      {
        key: "Permissions-Policy",
        value: "camera=(), microphone=(), geolocation=(), payment=()",
      },
      {
        key: "Content-Security-Policy",
        value: [
          "default-src 'self'",
          "base-uri 'self'",
          "object-src 'none'",
          "frame-ancestors 'none'",
          "img-src 'self' data: blob: https:",
          "script-src 'self' 'unsafe-inline' https://accounts.google.com https://maps.googleapis.com https://code.tidio.co",
          "style-src 'self' 'unsafe-inline'",
          "font-src 'self' data:",
          "connect-src 'self' https://accounts.google.com https://*.googleapis.com https://maps.googleapis.com https://*.tidio.co https://*.tidiochat.com https://*.tidio.io",
          "frame-src https://accounts.google.com https://www.google.com https://www.youtube-nocookie.com https://*.tidio.co https://*.tidiochat.com",
          "form-action 'self' https://checkout.stripe.com https://www.paypal.com https://www.sandbox.paypal.com",
        ].join("; "),
      },
      ...(process.env.NODE_ENV === "production"
        ? [
            {
              key: "Strict-Transport-Security",
              value: "max-age=31536000; includeSubDomains",
            },
          ]
        : []),
    ];

    return [{ source: "/:path*", headers: securityHeaders }];
  },
};

export default nextConfig;
