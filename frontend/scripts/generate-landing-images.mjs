import { mkdir, writeFile } from "node:fs/promises";
import path from "node:path";

/**
 * Generates landing page images with OpenAI and writes them to `public/landing/generated`.
 *
 * Usage:
 * - Set `OPENAI_API_KEY` in your shell environment (do not commit it).
 * - Run: `npm run generate:landing-images`
 *
 * Notes:
 * - Output files are meant to be committed as static assets.
 * - This script never prints or writes secrets.
 */
async function main() {
  const apiKey = process.env.OPENAI_API_KEY?.trim();
  if (!apiKey) {
    throw new Error("Missing OPENAI_API_KEY in the environment.");
  }

  if (typeof fetch !== "function") {
    throw new Error("Node.js 18+ is required (missing global fetch).");
  }

  const model = (process.env.OPENAI_IMAGE_MODEL?.trim() || "gpt-image-1.5").trim();
  const size = (process.env.OPENAI_IMAGE_SIZE?.trim() || "1536x1024").trim();

  const assets = [
    {
      file: "alfred-hero-dark.png",
      prompt:
        "A minimal, intellectual hero illustration for a knowledge workbench app. Dark background, subtle glow, abstract knowledge graph with nodes and edges, blueprint-like detail, modern, clean, high contrast, no text, no logos, no people.",
    },
    {
      file: "alfred-hero-light.png",
      prompt:
        "A minimal, intellectual hero illustration for a knowledge workbench app. Light background, subtle gradients, abstract knowledge graph with nodes and edges, blueprint-like detail, modern, clean, high contrast, no text, no logos, no people.",
    },
    {
      file: "alfred-blueprint-dark.png",
      prompt:
        "A minimal, intellectual system blueprint illustration. Dark background, layered boxes and arrows, subtle grid, modern UI aesthetic, no text, no logos, no people.",
    },
    {
      file: "alfred-blueprint-light.png",
      prompt:
        "A minimal, intellectual system blueprint illustration. Light background, layered boxes and arrows, subtle grid, modern UI aesthetic, no text, no logos, no people.",
    },
  ];

  const outDir = path.join(process.cwd(), "public", "landing", "generated");
  await mkdir(outDir, { recursive: true });

  for (const asset of assets) {
    const response = await fetch("https://api.openai.com/v1/images/generations", {
      method: "POST",
      headers: {
        Authorization: `Bearer ${apiKey}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        model,
        prompt: asset.prompt,
        size,
      }),
    });

    if (!response.ok) {
      const payload = await response.json().catch(() => null);
      const message = payload?.error?.message ?? `Request failed with status ${response.status}.`;
      throw new Error(message);
    }

    const payload = await response.json();
    const b64 = payload?.data?.[0]?.b64_json;
    if (typeof b64 !== "string" || !b64) {
      throw new Error("Image generation response missing base64 data.");
    }

    const filePath = path.join(outDir, asset.file);
    await writeFile(filePath, Buffer.from(b64, "base64"));
    process.stdout.write(`✓ Wrote ${path.relative(process.cwd(), filePath)}\n`);
  }
}

await main();

