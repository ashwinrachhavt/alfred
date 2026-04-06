"use client";

import { useState } from "react";
import { BookMarked, GraduationCap, Eye } from "lucide-react";
import { Button } from "@/components/ui/button";
import type { SaveIntent } from "@/lib/api/dictionary";

const intents: {
  value: SaveIntent;
  label: string;
  icon: typeof GraduationCap;
}[] = [
  { value: "learning", label: "Learning", icon: GraduationCap },
  { value: "reference", label: "Reference", icon: BookMarked },
  { value: "encountered", label: "Encountered", icon: Eye },
];

export function SaveBar({
  onSave,
  isSaving,
}: {
  onSave: (intent: SaveIntent) => void;
  isSaving?: boolean;
}) {
  const [selected, setSelected] = useState<SaveIntent>("learning");

  return (
    <div className="sticky bottom-0 z-10 flex items-center justify-between border-t bg-background/95 px-4 py-3 backdrop-blur-sm">
      <div className="flex gap-1.5">
        {intents.map(({ value, label, icon: Icon }) => (
          <button
            key={value}
            onClick={() => setSelected(value)}
            className={`flex items-center gap-1.5 rounded-md px-3 py-1.5 text-xs font-medium uppercase tracking-wider transition-colors ${
              selected === value
                ? "bg-[var(--alfred-accent-subtle)] text-foreground"
                : "text-muted-foreground hover:text-foreground"
            }`}
          >
            <Icon className="h-3.5 w-3.5" />
            {label}
          </button>
        ))}
      </div>
      <Button
        onClick={() => onSave(selected)}
        disabled={isSaving}
        size="sm"
        className="bg-[#E8590C] text-white hover:bg-[#E8590C]/90"
      >
        {isSaving ? "Saving..." : "Save to Vocabulary"}
      </Button>
    </div>
  );
}
