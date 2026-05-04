"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { CornerDownLeft, Search, Sparkles } from "lucide-react";
import { Input } from "@/components/ui/input";
import { useDictionarySearch } from "@/features/dictionary/queries";

export function DictionarySearchBar({ onLookup }: { onLookup: (word: string) => void }) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [localQuery, setLocalQuery] = useState("");
  const [debouncedQuery, setDebouncedQuery] = useState<string | null>(null);
  const [showDropdown, setShowDropdown] = useState(false);

  const { data: searchResult, isFetching } = useDictionarySearch(debouncedQuery);

  useEffect(() => {
    const timer = setTimeout(
      () => setDebouncedQuery(localQuery.length >= 2 ? localQuery : null),
      localQuery.length >= 2 ? 300 : 0,
    );
    return () => clearTimeout(timer);
  }, [localQuery]);

  const handleSelect = useCallback(
    (word: string) => {
      setLocalQuery(word);
      setShowDropdown(false);
      onLookup(word);
    },
    [onLookup],
  );

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && localQuery.trim()) {
      handleSelect(localQuery.trim().toLowerCase());
    }
    if (e.key === "Escape") {
      setShowDropdown(false);
    }
  };

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === "k") {
        e.preventDefault();
        inputRef.current?.focus();
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, []);

  const lookupSuggestion = localQuery.trim().toLowerCase();
  const showLookupSuggestion = showDropdown && lookupSuggestion.length >= 2;
  const savedResults = searchResult?.saved ?? [];
  const lookupPreview = searchResult?.lookup ?? null;

  return (
    <div className="relative mx-auto w-full max-w-2xl">
      <div className="bg-card/90 relative rounded-md border shadow-sm backdrop-blur transition-colors focus-within:border-[var(--alfred-accent-muted)]">
        <Search className="text-muted-foreground absolute top-1/2 left-4 h-5 w-5 -translate-y-1/2" />
        <Input
          ref={inputRef}
          value={localQuery}
          onChange={(e) => {
            setLocalQuery(e.target.value);
            setShowDropdown(true);
          }}
          onFocus={() => localQuery.length >= 2 && setShowDropdown(true)}
          onKeyDown={handleKeyDown}
          placeholder="Look up a word..."
          className="placeholder:text-muted-foreground/50 h-14 border-0 bg-transparent pr-24 pl-12 font-serif text-lg shadow-none focus-visible:ring-0"
        />
        <kbd className="bg-muted text-muted-foreground absolute top-1/2 right-4 -translate-y-1/2 rounded-sm border px-2 py-0.5 font-mono text-xs">
          {"\u2318"}K
        </kbd>
      </div>

      {showLookupSuggestion && (
        <div className="bg-popover/95 absolute top-full right-0 left-0 z-20 mt-2 overflow-hidden rounded-md border shadow-lg backdrop-blur">
          {savedResults.length > 0 && (
            <div className="p-2">
              <span className="text-muted-foreground px-2 font-mono text-[10px] tracking-wider uppercase">
                Your Vocabulary
              </span>
              {savedResults.map((item) => (
                <button
                  key={item.id}
                  onClick={() => handleSelect(item.word)}
                  className="hover:bg-accent mt-1 flex w-full items-center rounded px-2 py-1.5 text-left text-sm transition-colors"
                >
                  <span className="font-medium">{item.word}</span>
                  <span className="text-muted-foreground ml-auto font-mono text-[10px] uppercase">
                    {item.save_intent}
                  </span>
                </button>
              ))}
            </div>
          )}
          <div className={savedResults.length > 0 ? "border-t p-2" : "p-2"}>
            <span className="text-muted-foreground px-2 font-mono text-[10px] tracking-wider uppercase">
              Look Up
            </span>
            <button
              onClick={() => handleSelect(lookupSuggestion)}
              className="hover:bg-accent mt-1 flex w-full items-center gap-2 rounded-sm px-2 py-2 text-left text-sm transition-colors"
            >
              <Sparkles className="h-4 w-4 text-[var(--alfred-accent)]" />
              <span className="font-medium">{lookupSuggestion}</span>
              <span className="text-muted-foreground ml-auto flex items-center gap-1 font-mono text-[10px] tracking-wider uppercase">
                {isFetching ? "Checking" : "Return"}
                <CornerDownLeft className="h-3 w-3" />
              </span>
            </button>
          </div>
          {lookupPreview && lookupPreview.definitions.length > 0 && (
            <div className="border-t p-2">
              <span className="text-muted-foreground px-2 font-mono text-[10px] tracking-wider uppercase">
                Preview
              </span>
              <button
                onClick={() => handleSelect(lookupPreview.word)}
                className="hover:bg-accent mt-1 flex w-full items-center rounded px-2 py-1.5 text-left text-sm transition-colors"
              >
                <span className="font-medium">{lookupPreview.word}</span>
                <span className="text-muted-foreground ml-2 text-xs">
                  {lookupPreview.definitions[0]?.senses[0]?.definition.slice(0, 60)}
                  ...
                </span>
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
