import { NextResponse } from "next/server";
import { AI_MODELS, OPENAI_API_URL, supportsCustomTemperature } from "@/lib/constants/ai";
import { getAuth } from "@/lib/auth.server";

type ChatCompletionRequestBody = {
  model: string;
  messages: unknown;
  temperature?: number;
};

export async function POST(req: Request) {
  try {
    const { userId } = await getAuth();
    if (!userId) {
      return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
    }

    const { messages, temperature = 0.7 } = await req.json();
    const model = AI_MODELS.PROXY;
    const requestBody: ChatCompletionRequestBody = { model, messages };
    if (supportsCustomTemperature(model)) {
      requestBody.temperature = temperature;
    }

    const apiKey = process.env.OPENAI_API_KEY;
    if (!apiKey) {
      return NextResponse.json({ error: "Missing OPENAI_API_KEY" }, { status: 500 });
    }

    const response = await fetch(OPENAI_API_URL, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${apiKey}`,
      },
      body: JSON.stringify(requestBody),
    });

    if (!response.ok) {
      const error = await response.json();
      return NextResponse.json(
        { error: error.error?.message || "OpenAI API error" },
        { status: response.status },
      );
    }

    const data = await response.json();
    return NextResponse.json(data);
  } catch (error) {
    console.error("AI Request failed:", error);
    return NextResponse.json({ error: "Internal Server Error" }, { status: 500 });
  }
}
