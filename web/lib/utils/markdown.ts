export function markdownToPlainText(markdown: string): string {
  if (!markdown.trim()) return "";

  const text = markdown
    .replace(/\r\n?/g, "\n")
    .replace(/```(?:[\w-]+)?\n([\s\S]*?)```/g, "\n$1\n")
    .replace(/`([^`]+)`/g, "$1")
    .replace(/!\[([^\]]*)\]\([^)]+\)/g, "$1")
    .replace(/\[([^\]]+)\]\([^)]+\)/g, "$1")
    .replace(/\[\[([^[\]]+)\]\]/g, "$1")
    .replace(/^ {0,3}#{1,6}\s+/gm, "")
    .replace(/^ {0,3}>\s?/gm, "")
    .replace(/^ {0,3}[-*+]\s+\[(?: |x|X)\]\s+/gm, "")
    .replace(/^ {0,3}[-*+]\s+/gm, "")
    .replace(/^ {0,3}\d+\.\s+/gm, "")
    .replace(/^ {0,3}(-{3,}|\*{3,}|_{3,})\s*$/gm, "")
    .replace(/(\*\*|__)(.*?)\1/g, "$2")
    .replace(/(\*|_)(.*?)\1/g, "$2")
    .replace(/~~(.*?)~~/g, "$1")
    .replace(/^\|/gm, "")
    .replace(/\|$/gm, "")
    .replace(/\|/g, " ");

  return text
    .split("\n")
    .map((line) => line.trim())
    .filter(Boolean)
    .join(" ")
    .replace(/\s+/g, " ")
    .trim();
}

export function createMarkdownPreview(markdown: string, maxLength = 180): string {
  const text = markdownToPlainText(markdown);
  if (text.length <= maxLength) return text;
  return `${text.slice(0, maxLength).trimEnd()}…`;
}
