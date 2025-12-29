/** @type {import("next").NextConfig} */
const nextConfig = {
  async rewrites() {
    const normalizeApiBaseUrl = (raw) => raw.trim().replace(/\/+$/, "");

    const configured = process.env.ALFRED_API_BASE_URL?.trim();
    if (configured) {
      return [
        {
          source: "/api/:path*",
          destination: `${normalizeApiBaseUrl(configured)}/api/:path*`,
        },
      ];
    }

    if (process.env.NODE_ENV !== "production") {
      return [
        {
          source: "/api/:path*",
          destination: "http://localhost:8000/api/:path*",
        },
      ];
    }

    return [];
  },
};

module.exports = nextConfig;

