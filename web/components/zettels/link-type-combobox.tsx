"use client";

import { useMemo, useState } from "react";
import { Check, ChevronDown } from "lucide-react";

import { Input } from "@/components/ui/input";
import { useLinkTypes } from "@/features/zettels/queries";
import { SEED_LINK_TYPES } from "@/lib/constants/zettel-link-types";
import { cn } from "@/lib/utils";

type Option = { type: string; label: string; count?: number; curated: boolean };

type Props = {
  value: string;
  onChange: (type: string) => void;
};

export function LinkTypeCombobox({ value, onChange }: Props) {
  const [open, setOpen] = useState(false);
  const [input, setInput] = useState(value);
  const { data: dynamicTypes = [] } = useLinkTypes();

  const options = useMemo<Option[]>(() => {
    const seen = new Set<string>();
    const merged: Option[] = [];
    for (const s of SEED_LINK_TYPES) {
      merged.push({ type: s.type, label: s.label, curated: true });
      seen.add(s.type);
    }
    for (const d of dynamicTypes) {
      if (seen.has(d.type)) continue;
      merged.push({ type: d.type, label: d.type, count: d.count, curated: false });
      seen.add(d.type);
    }
    return merged;
  }, [dynamicTypes]);

  const filtered = useMemo(() => {
    const q = input.trim().toLowerCase();
    if (!q) return options;
    return options.filter((o) => o.type.includes(q) || o.label.toLowerCase().includes(q));
  }, [options, input]);

  const commit = (next: string) => {
    const normalized = next.trim().toLowerCase();
    if (!normalized) return;
    onChange(normalized);
    setInput(normalized);
    setOpen(false);
  };

  return (
    <div className="relative">
      <div className="flex items-center gap-1">
        <Input
          value={input}
          onFocus={() => setOpen(true)}
          onChange={(e) => {
            setInput(e.target.value);
            setOpen(true);
          }}
          onKeyDown={(e) => {
            if (e.key === "Enter") {
              e.preventDefault();
              commit(input);
            } else if (e.key === "Escape") {
              setOpen(false);
            }
          }}
          onBlur={() => window.setTimeout(() => setOpen(false), 120)}
          placeholder="related, supports, contradicts…"
          className="pr-7 font-mono text-[12px]"
        />
        <ChevronDown
          size={12}
          className="text-muted-foreground pointer-events-none absolute top-1/2 right-2.5 -translate-y-1/2"
        />
      </div>
      {open && filtered.length > 0 && (
        <div className="bg-popover absolute top-full right-0 left-0 z-50 mt-1 max-h-48 overflow-y-auto rounded-md border shadow-md">
          {filtered.map((opt) => (
            <button
              key={opt.type}
              type="button"
              onMouseDown={(e) => {
                e.preventDefault();
                commit(opt.type);
              }}
              className={cn(
                "flex w-full items-center justify-between gap-2 px-3 py-1.5 text-left text-xs",
                value === opt.type && "bg-accent",
              )}
            >
              <span className="flex items-center gap-2">
                {value === opt.type ? (
                  <Check size={10} className="text-primary" />
                ) : (
                  <span className="w-[10px]" />
                )}
                <span className="font-mono">{opt.type}</span>
                {opt.curated && (
                  <span className="text-muted-foreground text-[10px] uppercase tracking-wider">
                    suggested
                  </span>
                )}
              </span>
              {opt.count !== undefined && (
                <span className="text-muted-foreground font-mono text-[10px]">
                  {opt.count}
                </span>
              )}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
