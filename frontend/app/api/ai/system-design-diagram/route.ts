import { NextResponse } from "next/server";

type GenerateDiagramRequest = {
  prompt: string;
  problemStatement?: string;
};

type GenerateDiagramResponse = {
  mermaid: string;
};

const MODEL = "gpt-5.2";

function isNonEmptyString(value: unknown): value is string {
  return typeof value === "string" && value.trim().length > 0;
}

export async function POST(req: Request) {
  try {
    const body = (await req.json()) as Partial<GenerateDiagramRequest>;
    if (!isNonEmptyString(body.prompt)) {
      return NextResponse.json({ error: "Missing prompt" }, { status: 400 });
    }

    const apiKey = process.env.OPENAI_API_KEY;
    if (!apiKey) {
      return NextResponse.json({ error: "Missing OPENAI_API_KEY" }, { status: 500 });
    }

    const problemStatement =
      typeof body.problemStatement === "string" ? body.problemStatement.trim() : "";

    const system = [
      "You generate Mermaid diagrams for system design.",
      'Return ONLY valid JSON: {"mermaid": "<mermaid>"}',
      "The mermaid must be plain Mermaid syntax (no ``` fences).",
      "Prefer flowchart TD for architecture diagrams.",
      "Keep it concise and readable: <= 20 nodes, use subgraphs for layers.",
      "Use short labels; avoid emojis; avoid overly long text.",
      "If the prompt is ambiguous, make reasonable assumptions.",
    ].join("\n");

    const user = [
      problemStatement ? `Problem statement:\n${problemStatement}` : null,
      `Prompt:\n${body.prompt.trim()}`,
    ]
      .filter(Boolean)
      .join("\n\n");

    const response = await fetch("https://api.openai.com/v1/chat/completions", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${apiKey}`,
      },
      body: JSON.stringify({
        model: MODEL,
        temperature: 0.2,
        response_format: { type: "json_object" },
        messages: [
          { role: "system", content: system },
          { role: "user", content: user },
        ],
      }),
    });

    if (!response.ok) {
      const errorPayload = await response.json().catch(() => null);
      return NextResponse.json(
        { error: errorPayload?.error?.message ?? "OpenAI API error" },
        { status: response.status },
      );
    }

    const data = (await response.json()) as {
      choices?: Array<{ message?: { content?: string } }>;
    };
    const content = data.choices?.[0]?.message?.content ?? "";

    let parsed: unknown;
    try {
      parsed = JSON.parse(content);
    } catch {
      parsed = null;
    }

    const mermaid =
      typeof parsed === "object" &&
      parsed !== null &&
      "mermaid" in parsed &&
      typeof (parsed as { mermaid?: unknown }).mermaid === "string"
        ? (parsed as { mermaid: string }).mermaid.trim()
        : "";

    if (!mermaid) {
      return NextResponse.json(
        { error: "Model did not return mermaid" },
        { status: 502 },
      );
    }

    const payload: GenerateDiagramResponse = { mermaid };
    return NextResponse.json(payload);
  } catch (error) {
    console.error("AI diagram generation failed:", error);
    return NextResponse.json({ error: "Internal Server Error" }, { status: 500 });
  }
}

