import type { NextConfig } from "next";

function normalizeApiBaseUrl(raw: string): string {
  return raw.trim().replace(/\/+$/, "");
}

function getApiBaseUrl(): string | null {
  const configured = process.env.ALFRED_API_BASE_URL?.trim();
  if (configured) return normalizeApiBaseUrl(configured);

  // Local dev default: FastAPI runs on :8000 (see repo README).
  if (process.env.NODE_ENV !== "production") return "http://localhost:8000";

  return null;
}

const nextConfig: NextConfig = {
  async rewrites() {
    const apiBaseUrl = getApiBaseUrl();
    if (!apiBaseUrl) return [];

    return [
      {
        source: "/api/:path*",
        destination: `${apiBaseUrl}/api/:path*`,
      },
    ];
  },
};

export default nextConfig;
