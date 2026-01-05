/** @type {import("next").NextConfig} */
const nextConfig = {
  async rewrites() {
    const normalizeApiBaseUrl = (raw) => raw.trim().replace(/\/+$/, "");

    const configured = process.env.ALFRED_API_BASE_URL?.trim();
    const apiBaseUrl = configured
      ? normalizeApiBaseUrl(configured)
      : process.env.NODE_ENV !== "production"
        ? "http://localhost:8000"
        : null;

    if (!apiBaseUrl) return [];

    return [
      // Some FastAPI routers are mounted outside `/api/*` on the backend.
      // Keep the frontend consistent by always calling `/api/*` and rewriting.
      { source: "/api/company/:path*", destination: `${apiBaseUrl}/company/:path*` },
      { source: "/api/tasks/:path*", destination: `${apiBaseUrl}/tasks/:path*` },
      { source: "/api/rag/:path*", destination: `${apiBaseUrl}/rag/:path*` },
      { source: "/api/:path*", destination: `${apiBaseUrl}/api/:path*` },
    ];
  },
};

module.exports = nextConfig;
