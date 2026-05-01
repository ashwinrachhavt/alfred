const LEADING_INDENT = /^[\t ]*/;
const TRAILING_WHITESPACE = /[ \t]+$/;
const NON_BREAKING_SPACES = /\u00a0/g;
const ZERO_WIDTH_CHARACTERS = /[\u200b-\u200d\uFEFF]/g;

function getCommonIndent(lines: string[]): number {
  let commonIndent: number | null = null;

  for (const line of lines) {
    if (!line) continue;

    const indent = line.match(LEADING_INDENT)?.[0].length ?? 0;
    if (indent === line.length) continue;

    commonIndent = commonIndent === null ? indent : Math.min(commonIndent, indent);
    if (commonIndent === 0) {
      return 0;
    }
  }

  return commonIndent ?? 0;
}

export function normalizePastedEditorText(text: string): string {
  if (!text) return text;

  const normalized = text
    .replace(/\r\n?/g, "\n")
    .replace(NON_BREAKING_SPACES, " ")
    .replace(ZERO_WIDTH_CHARACTERS, "");

  if (!normalized.includes("\n")) {
    return normalized;
  }

  const lines = normalized.split("\n").map((line) => {
    const withoutTrailingWhitespace = line.replace(TRAILING_WHITESPACE, "");
    return withoutTrailingWhitespace.trim() ? withoutTrailingWhitespace : "";
  });

  let start = 0;
  let end = lines.length;

  while (start < end && lines[start] === "") {
    start += 1;
  }

  while (end > start && lines[end - 1] === "") {
    end -= 1;
  }

  const trimmedLines = lines.slice(start, end);
  if (!trimmedLines.length) {
    return "";
  }

  const commonIndent = getCommonIndent(trimmedLines);
  if (commonIndent === 0) {
    return trimmedLines.join("\n");
  }

  return trimmedLines.map((line) => (line ? line.slice(commonIndent) : "")).join("\n");
}
