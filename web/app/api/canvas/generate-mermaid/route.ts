import { NextResponse } from "next/server";

import { getAuth } from "@/lib/auth.server";

function getApiBaseUrl(): string {
  const configured = process.env.ALFRED_API_BASE_URL?.trim();
  const fallback = process.env.NODE_ENV !== "production" ? "http://localhost:8000" : "";
  return (configured || fallback).replace(/\/+$/, "");
}

export async function POST(req: Request) {
  try {
    const { userId } = await getAuth();
    if (!userId) {
      return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
    }

    const apiBaseUrl = getApiBaseUrl();
    if (!apiBaseUrl) {
      return NextResponse.json({ error: "Backend API is not configured" }, { status: 500 });
    }

    const response = await fetch(`${apiBaseUrl}/api/canvas/generate-mermaid`, {
      method: "POST",
      headers: {
        "Content-Type": req.headers.get("content-type") ?? "application/json",
      },
      body: await req.text(),
      cache: "no-store",
    });

    const contentType = response.headers.get("content-type") ?? "";
    const payload = contentType.includes("application/json")
      ? await response.json().catch(() => null)
      : null;

    return NextResponse.json(
      payload ?? { error: response.ok ? "Empty backend response" : "Backend request failed" },
      { status: response.status },
    );
  } catch (error) {
    console.error("Canvas Mermaid proxy failed:", error);
    return NextResponse.json({ error: "Internal Server Error" }, { status: 500 });
  }
}
