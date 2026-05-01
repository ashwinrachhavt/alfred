export const OPENAI_API_URL = "https://api.openai.com/v1/chat/completions";
export const DEFAULT_AI_MODEL = "gpt-5.5";

export const AI_MODELS = {
  PROXY: DEFAULT_AI_MODEL,
  SYSTEM_DESIGN: "gpt-4o",
  DIAGRAM: "gpt-4o",
} as const;

const DEFAULT_TEMPERATURE_UNSUPPORTED_PREFIXES = ["gpt-5", "o1", "o3", "o4"] as const;

export function supportsCustomTemperature(model: string): boolean {
  const normalized = model.trim().toLowerCase();
  return !DEFAULT_TEMPERATURE_UNSUPPORTED_PREFIXES.some((prefix) =>
    normalized.startsWith(prefix),
  );
}
