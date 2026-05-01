"use client";

import { useCallback, useMemo, useState } from "react";
import { toast } from "sonner";
import { CheckSquareIcon, FileTextIcon, GraduationCapIcon } from "lucide-react";

import {
  CommandDialog,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
  CommandShortcut,
} from "@/components/ui/command";

import { useCreateTodayEntry } from "@/features/today/mutations";
import { toIsoDay } from "@/features/today/queries";
import type { DailyEntryCreate } from "@/features/today/types";
import { useTodayInteraction } from "./today-interaction-context";

type QuickAddKind = Exclude<DailyEntryCreate["kind"], never>;

interface QuickCommand {
  kind: QuickAddKind;
  label: string;
  icon: React.ComponentType<{ className?: string }>;
  shortcut: string;
}

const COMMANDS: QuickCommand[] = [
  { kind: "todo", label: "Add todo", icon: CheckSquareIcon, shortcut: "T" },
  { kind: "note", label: "Add note", icon: FileTextIcon, shortcut: "N" },
  { kind: "learning", label: "Add learning", icon: GraduationCapIcon, shortcut: "L" },
];

export function CommandBar() {
  const { commandBarOpen, closeCommandBar } = useTodayInteraction();
  const createMutation = useCreateTodayEntry();
  const [query, setQuery] = useState("");

  const trimmed = query.trim();

  const runCommand = useCallback(
    async (kind: QuickAddKind, title: string) => {
      const cleaned = title.trim();
      if (!cleaned) {
        toast.error("Type a title first");
        return;
      }
      try {
        await createMutation.mutateAsync({
          entry_date: toIsoDay(new Date()),
          kind,
          title: cleaned,
        });
        toast.success("Entry created");
        setQuery("");
        closeCommandBar();
      } catch {
        toast.error("Failed to create entry");
      }
    },
    [closeCommandBar, createMutation],
  );

  const placeholder = useMemo(
    () => "Add a todo, note, or learning for today…",
    [],
  );

  return (
    <CommandDialog
      open={commandBarOpen}
      onOpenChange={(v) => {
        if (!v) closeCommandBar();
      }}
      contentClassName="border-[var(--alfred-ruled-line)]"
    >
      <CommandInput
        value={query}
        onValueChange={setQuery}
        placeholder={placeholder}
      />
      <CommandList>
        <CommandEmpty>
          <span className="font-mono text-xs uppercase tracking-widest text-[var(--alfred-text-tertiary)]">
            Start typing to add an entry
          </span>
        </CommandEmpty>
        <CommandGroup
          heading="Quick add"
          className="[&_[cmdk-group-heading]]:font-mono [&_[cmdk-group-heading]]:uppercase [&_[cmdk-group-heading]]:tracking-widest"
        >
          {COMMANDS.map((cmd) => {
            const Icon = cmd.icon;
            const displayTitle = trimmed || "…";
            return (
              <CommandItem
                key={cmd.kind}
                value={`${cmd.kind} ${displayTitle}`}
                onSelect={() => void runCommand(cmd.kind, trimmed)}
              >
                <Icon className="mr-2 size-4 text-[var(--alfred-text-tertiary)]" aria-hidden="true" />
                <span className="text-sm">
                  <span className="text-[var(--alfred-text-tertiary)]">
                    {cmd.label}:
                  </span>{" "}
                  <span className="text-foreground">{displayTitle}</span>
                </span>
                <CommandShortcut className="font-mono">{cmd.shortcut}</CommandShortcut>
              </CommandItem>
            );
          })}
        </CommandGroup>
      </CommandList>
    </CommandDialog>
  );
}
