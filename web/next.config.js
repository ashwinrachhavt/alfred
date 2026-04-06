/** @type {import("next").NextConfig} */
const nextConfig = {
  turbopack: {
    root: __dirname,
  },
  compiler: {
    removeConsole: process.env.NODE_ENV === "production" ? { exclude: ["error", "warn"] } : false,
  },
  experimental: {
    optimizePackageImports: [
      "lucide-react",
      "@radix-ui/react-dialog",
      "@radix-ui/react-dropdown-menu",
      "@radix-ui/react-popover",
      "@radix-ui/react-tooltip",
      "date-fns",
    ],
  },
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
      { source: "/api/research", destination: `${apiBaseUrl}/research/` },
      { source: "/api/research/:path*", destination: `${apiBaseUrl}/research/:path*` },
      { source: "/api/:path*", destination: `${apiBaseUrl}/api/:path*` },
    ];
  },
};

module.exports = nextConfig;
