import { useCallback, useState } from "react";

export function usePasteDetection() {
  // State
  const [isPasteMode, setIsPasteMode] = useState(false);
  const [pastedText, setPastedText] = useState("");
  const [tokenEstimate, setTokenEstimate] = useState(0);

  // Handlers
  const handlePaste = useCallback((e: React.ClipboardEvent<HTMLTextAreaElement>) => {
    const text = e.clipboardData.getData("text/plain");
    if (text.length > 100) {  // threshold
      setIsPasteMode(true);
      setPastedText(text);
      setTokenEstimate(Math.ceil(text.split(/\s+/).length * 1.3));
    }
  }, []);

  const extractTitle = useCallback((text: string): string => {
    const firstLine = text.split("\n").find((l) => l.trim().length > 0)?.trim() || "";
    return firstLine.length > 120 ? firstLine.slice(0, 117) + "..." : firstLine;
  }, []);

  const reset = useCallback(() => {
    setIsPasteMode(false);
    setPastedText("");
    setTokenEstimate(0);
  }, []);

  return { isPasteMode, pastedText, tokenEstimate, handlePaste, extractTitle, reset };
}
