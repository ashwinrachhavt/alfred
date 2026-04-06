"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { Search } from "lucide-react";
import { Input } from "@/components/ui/input";
import { useDictionarySearch } from "@/features/dictionary/queries";

export function DictionarySearchBar({
  onLookup,
}: {
  onLookup: (word: string) => void;
}) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [localQuery, setLocalQuery] = useState("");
  const [debouncedQuery, setDebouncedQuery] = useState<string | null>(null);
  const [showDropdown, setShowDropdown] = useState(false);

  const { data: searchResult } = useDictionarySearch(debouncedQuery);

  useEffect(() => {
    if (localQuery.length < 2) {
      setDebouncedQuery(null);
      return;
    }
    const timer = setTimeout(() => setDebouncedQuery(localQuery), 300);
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

  return (
    <div className="relative w-full max-w-2xl mx-auto">
      <div className="relative">
        <Search className="absolute left-4 top-1/2 h-5 w-5 -translate-y-1/2 text-muted-foreground" />
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
          className="h-14 pl-12 pr-20 text-lg font-serif placeholder:text-muted-foreground/50"
        />
        <kbd className="absolute right-4 top-1/2 -translate-y-1/2 rounded border bg-muted px-2 py-0.5 font-mono text-xs text-muted-foreground">
          {"\u2318"}K
        </kbd>
      </div>

      {showDropdown && searchResult && (
        <div className="absolute top-full left-0 right-0 z-20 mt-1 rounded-md border bg-popover shadow-lg">
          {searchResult.saved.length > 0 && (
            <div className="p-2">
              <span className="px-2 font-mono text-[10px] uppercase tracking-wider text-muted-foreground">
                Your Vocabulary
              </span>
              {searchResult.saved.map((item) => (
                <button
                  key={item.id}
                  onClick={() => handleSelect(item.word)}
                  className="mt-1 flex w-full items-center rounded px-2 py-1.5 text-left text-sm hover:bg-accent transition-colors"
                >
                  <span className="font-medium">{item.word}</span>
                  <span className="ml-auto font-mono text-[10px] uppercase text-muted-foreground">
                    {item.save_intent}
                  </span>
                </button>
              ))}
            </div>
          )}
          {searchResult.lookup.definitions.length > 0 && (
            <div className="border-t p-2">
              <span className="px-2 font-mono text-[10px] uppercase tracking-wider text-muted-foreground">
                Look Up
              </span>
              <button
                onClick={() => handleSelect(searchResult.lookup.word)}
                className="mt-1 flex w-full items-center rounded px-2 py-1.5 text-left text-sm hover:bg-accent transition-colors"
              >
                <span className="font-medium">
                  {searchResult.lookup.word}
                </span>
                <span className="ml-2 text-xs text-muted-foreground">
                  {searchResult.lookup.definitions[0]?.senses[0]?.definition.slice(
                    0,
                    60,
                  )}
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
