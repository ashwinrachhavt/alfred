import { apiFetchResponse } from "@/lib/api/client";

function backendUrl(): string {
  const configured = process.env.ALFRED_API_BASE_URL?.trim().replace(/\/+$/, "");
  if (configured) return configured;
  return process.env.NODE_ENV !== "production" ? "http://localhost:8000" : "";
}

export async function GET() {
  const baseUrl = backendUrl();
  if (!baseUrl) {
    return Response.json({ detail: "ALFRED_API_BASE_URL is not configured" }, { status: 500 });
  }

  const response = await apiFetchResponse(`${baseUrl}/openapi.json`, { cache: "no-store" });
  const body = await response.text();

  return new Response(body, {
    status: response.status,
    statusText: response.statusText,
    headers: {
      "content-type": response.headers.get("content-type") ?? "application/json",
    },
  });
}
