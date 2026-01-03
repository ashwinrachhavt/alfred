// Client for AI Assist features using Next.js proxy

// We define a separate client function that calls our Next.js API route (frontend backend)
// instead of the Python backend, as requested by the user.

async function callOpenAIProxy(messages: { role: string; content: string }[], temperature = 0.7): Promise<string> {
    const res = await fetch("/api/ai/proxy", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ messages, temperature }),
    });

    if (!res.ok) {
        throw new Error(`AI request failed: ${res.statusText}`);
    }

    const data = await res.json();
    return data.choices?.[0]?.message?.content || "";
}

export async function completeText(
    text: string,
    contextBefore = "",
    contextAfter = ""
): Promise<string> {
    const prompt = `You are a helpful AI writing assistant. Complete the following text naturally.
Context before: "${contextBefore.slice(-500)}"
Current text: "${text}"
Context after: "${contextAfter.slice(0, 500)}"

Provide ONLY the completion text, no conversational filler.`;

    return callOpenAIProxy([{ role: "user", content: prompt }], 0.3);
}

export async function rewriteText(text: string, instruction = "Improve clarity and grammar"): Promise<string> {
    const prompt = `You are an expert editor. Rewrite the following text according to these instructions: "${instruction}".

Text to rewrite:
"${text}"

Provide ONLY the rewritten text, no conversational filler.`;

    return callOpenAIProxy([{ role: "user", content: prompt }], 0.3);
}

export async function summarizeText(text: string): Promise<string> {
    const prompt = `You are a helpful assistant. Summarize the following text concisely.

Text to summarize:
"${text}"

Provide ONLY the summary, no conversational filler.`;

    return callOpenAIProxy([{ role: "user", content: prompt }], 0.3);
}
