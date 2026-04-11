"use client";

import * as React from "react";
import { useRouter } from "next/navigation";
import { useTheme } from "next-themes";
import {
  BookOpen,
  ListChecks,
  Moon,
  Network,
  NotebookPen,
  Play,
  Plus,
  RefreshCw,
  Search,
  Sparkles,
  Sun,
} from "lucide-react";
import { toast } from "sonner";

import { useQueryClient } from "@tanstack/react-query";

import { pillars } from "@/lib/navigation";
import { useShellStore } from "@/lib/stores/shell-store";
import { cn } from "@/lib/utils";
import { apiPostJson } from "@/lib/api/client";
import { apiRoutes } from "@/lib/api/routes";
import { useTaskTracker } from "@/features/tasks/task-tracker-provider";

import { Button } from "@/components/ui/button";
import {
  CommandDialog,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
  CommandSeparator,
  CommandShortcut,
} from "@/components/ui/command";

type AppCommandPaletteContextValue = {
  open: boolean;
  setOpen: (open: boolean) => void;
  openPalette: () => void;
};

const AppCommandPaletteContext = React.createContext<AppCommandPaletteContextValue | null>(null);

function useAppCommandPaletteContext(): AppCommandPaletteContextValue {
  const ctx = React.useContext(AppCommandPaletteContext);
  if (!ctx) {
    throw new Error("useAppCommandPalette must be used within AppCommandPaletteProvider.");
  }
  return ctx;
}

function isEditableTarget(target: EventTarget | null): boolean {
  if (!target || !(target instanceof HTMLElement)) return false;
  const tagName = target.tagName;
  if (tagName === "INPUT" || tagName === "TEXTAREA" || tagName === "SELECT") return true;
  return target.isContentEditable;
}

function usePlatformShortcut(): string {
  const [shortcut, setShortcut] = React.useState("Ctrl K");

  React.useEffect(() => {
    const isApplePlatform =
      typeof navigator !== "undefined" && /Mac|iPhone|iPad|iPod/i.test(navigator.platform);
    setShortcut(isApplePlatform ? "⌘K" : "Ctrl K");
  }, []);

  return shortcut;
}

function useThemeToggleShortcut(): string {
  const [shortcut, setShortcut] = React.useState("Ctrl Shift L");

  React.useEffect(() => {
    const isApplePlatform =
      typeof navigator !== "undefined" && /Mac|iPhone|iPad|iPod/i.test(navigator.platform);
    setShortcut(isApplePlatform ? "⌘⇧L" : "Ctrl Shift L");
  }, []);

  return shortcut;
}

function AppCommandPaletteDialog({
  open,
  onOpenChange,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  const router = useRouter();
  const { resolvedTheme, setTheme } = useTheme();
  const { activeCount, setTaskCenterOpen, trackTask } = useTaskTracker();
  const queryClient = useQueryClient();
  const platformShortcut = usePlatformShortcut();
  const themeShortcut = useThemeToggleShortcut();
  const [query, setQuery] = React.useState("");

  // In-memory zettel search from React Query cache
  const zettelMatches = React.useMemo(() => {
    if (!query || query.length < 2) return [];
    const cached = queryClient.getQueryData<Array<{ id: string | number; title?: string }>>([
      "zettels",
      "cards",
    ]);
    if (!Array.isArray(cached)) return [];
    const q = query.toLowerCase();
    return cached.filter((z) => z.title?.toLowerCase().includes(q)).slice(0, 8);
  }, [query, queryClient]);

  React.useEffect(() => {
    if (!open) setQuery("");
  }, [open]);

  const toggleTheme = React.useCallback(() => {
    const isDark = resolvedTheme === "dark";
    setTheme(isDark ? "light" : "dark");
  }, [resolvedTheme, setTheme]);

  const navigateTo = React.useCallback(
    (href: string) => {
      onOpenChange(false);
      router.push(href);
    },
    [onOpenChange, router],
  );

  const triggerBulkEnrich = React.useCallback(async () => {
    onOpenChange(false);
    try {
      const res = await apiPostJson<
        { queued: number; tasks: { doc_id: string; task_id: string }[] },
        Record<string, never>
      >(apiRoutes.pipeline.replayBatch, {});
      const firstTask = res.tasks?.[0];
      if (firstTask?.task_id) {
        trackTask({ id: firstTask.task_id, label: "Bulk Enrich", source: "generic" });
      }
      toast.success("Bulk enrich started");
    } catch {
      toast.error("Failed to start bulk enrich");
    }
  }, [onOpenChange, trackTask]);

  const triggerReclassify = React.useCallback(async () => {
    onOpenChange(false);
    try {
      const res = await apiPostJson<{ task_id: string }, Record<string, never>>(
        apiRoutes.taxonomy.reclassifyAll,
        {},
      );
      if (res.task_id) {
        trackTask({ id: res.task_id, label: "Reclassify All Zettels", source: "generic" });
      }
      toast.success("Reclassify started");
    } catch {
      toast.error("Failed to start reclassify");
    }
  }, [onOpenChange, trackTask]);

  return (
    <CommandDialog open={open} onOpenChange={onOpenChange} contentClassName="max-w-xl">
      <CommandInput
        placeholder="Search Alfred..."
        value={query}
        onValueChange={setQuery}
        autoFocus
      />
      <CommandList>
        <CommandEmpty>No matches.</CommandEmpty>

        <CommandGroup heading="Navigation">
          {pillars.map((p) => {
            if (p.key === "ai") {
              return (
                <CommandItem
                  key={p.key}
                  value="ask alfred assistant rag chat knowledge ai"
                  onSelect={() => {
                    useShellStore.getState().openAiPanel("expanded");
                    onOpenChange(false);
                  }}
                >
                  <Sparkles className="h-4 w-4" aria-hidden="true" />
                  <span>Ask Alfred</span>
                  <CommandShortcut>⌘J</CommandShortcut>
                </CommandItem>
              );
            }
            return (
              <CommandItem
                key={p.key}
                value={`${p.title} ${p.key}`}
                onSelect={() => navigateTo(p.href)}
              >
                <p.icon className="h-4 w-4" aria-hidden="true" />
                <span>{p.title}</span>
                <CommandShortcut>⌘{p.shortcut}</CommandShortcut>
              </CommandItem>
            );
          })}
        </CommandGroup>

        <CommandSeparator />

        <CommandGroup heading="Create">
          <CommandItem
            value="create zettel knowledge card new"
            onSelect={() => {
              navigateTo("/knowledge?create=true");
            }}
          >
            <Plus className="h-4 w-4" aria-hidden="true" />
            <span>Create Zettel</span>
          </CommandItem>
          <CommandItem
            value="create note new write"
            onSelect={() => {
              useShellStore.getState().openToolPanel("notes");
              onOpenChange(false);
            }}
          >
            <NotebookPen className="h-4 w-4" aria-hidden="true" />
            <span>Create Note</span>
            <CommandShortcut>⌘N</CommandShortcut>
          </CommandItem>
        </CommandGroup>

        <CommandSeparator />

        {zettelMatches.length > 0 && (
          <>
            <CommandGroup heading="Zettels">
              {zettelMatches.map((z) => (
                <CommandItem
                  key={z.id}
                  value={`zettel ${z.title ?? z.id}`}
                  onSelect={() => navigateTo(`/knowledge?zettel=${z.id}`)}
                >
                  <BookOpen className="h-4 w-4" aria-hidden="true" />
                  <span className="truncate">{z.title ?? `Zettel #${z.id}`}</span>
                </CommandItem>
              ))}
            </CommandGroup>
            <CommandSeparator />
          </>
        )}

        <CommandGroup heading="Tools">
          <CommandItem
            value="connectors integrations sources"
            onSelect={() => {
              useShellStore.getState().openToolPanel("connectors");
              onOpenChange(false);
            }}
          >
            <Network className="h-4 w-4" aria-hidden="true" />
            <span>Connectors</span>
          </CommandItem>
        </CommandGroup>

        <CommandSeparator />

        <CommandGroup heading="Workflows">
          <CommandItem value="bulk enrich documents pipeline replay" onSelect={triggerBulkEnrich}>
            <Play className="h-4 w-4" aria-hidden="true" />
            <span>Bulk Enrich Documents</span>
          </CommandItem>
          <CommandItem value="reclassify all zettels taxonomy" onSelect={triggerReclassify}>
            <RefreshCw className="h-4 w-4" aria-hidden="true" />
            <span>Reclassify All Zettels</span>
          </CommandItem>
        </CommandGroup>

        <CommandSeparator />

        <CommandGroup heading="Tasks">
          <CommandItem
            value="task center background tasks"
            onSelect={() => {
              setTaskCenterOpen(true);
              onOpenChange(false);
            }}
          >
            <ListChecks className="h-4 w-4" aria-hidden="true" />
            <span>Task center</span>
            {activeCount ? <CommandShortcut>{activeCount} active</CommandShortcut> : null}
          </CommandItem>
        </CommandGroup>

        <CommandSeparator />

        <CommandGroup heading="Preferences">
          <CommandItem
            value="toggle theme"
            onSelect={() => {
              toggleTheme();
              onOpenChange(false);
            }}
          >
            {resolvedTheme === "dark" ? (
              <Sun className="h-4 w-4" aria-hidden="true" />
            ) : (
              <Moon className="h-4 w-4" aria-hidden="true" />
            )}
            <span>Toggle theme</span>
            <CommandShortcut>{themeShortcut}</CommandShortcut>
          </CommandItem>
        </CommandGroup>
      </CommandList>

      <div className="text-muted-foreground flex items-center justify-between border-t px-3 py-2 text-xs">
        <span>Open with {platformShortcut}</span>
        <span className="hidden sm:inline">Use ↑ ↓ and Enter</span>
      </div>
    </CommandDialog>
  );
}

export function AppCommandPaletteProvider({ children }: { children: React.ReactNode }) {
  const [open, setOpen] = React.useState(false);
  const { resolvedTheme, setTheme } = useTheme();

  const openPalette = React.useCallback(() => setOpen(true), []);
  const toggleTheme = React.useCallback(() => {
    const isDark = resolvedTheme === "dark";
    setTheme(isDark ? "light" : "dark");
  }, [resolvedTheme, setTheme]);

  React.useEffect(() => {
    function onKeyDown(event: KeyboardEvent) {
      if (event.defaultPrevented) return;
      if (isEditableTarget(event.target)) return;

      const key = event.key.toLowerCase();
      if ((event.metaKey || event.ctrlKey) && event.shiftKey && key === "l") {
        event.preventDefault();
        toggleTheme();
        return;
      }
      if ((event.metaKey || event.ctrlKey) && key === "k") {
        event.preventDefault();
        setOpen(true);
        return;
      }

      if (key === "/") {
        event.preventDefault();
        setOpen(true);
      }
    }

    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [toggleTheme]);

  const value = React.useMemo<AppCommandPaletteContextValue>(
    () => ({ open, setOpen, openPalette }),
    [open, openPalette],
  );

  return (
    <AppCommandPaletteContext.Provider value={value}>
      {children}
      <AppCommandPaletteDialog open={open} onOpenChange={setOpen} />
    </AppCommandPaletteContext.Provider>
  );
}

export function useAppCommandPalette() {
  return useAppCommandPaletteContext();
}

export function AppCommandPaletteTrigger({
  className,
  variant = "default",
}: {
  className?: string;
  variant?: "default" | "icon";
}) {
  const { openPalette } = useAppCommandPaletteContext();
  const platformShortcut = usePlatformShortcut();

  if (variant === "icon") {
    return (
      <Button
        type="button"
        variant="ghost"
        size="icon"
        className={className}
        aria-label="Open command palette"
        onClick={openPalette}
      >
        <Search className="h-4 w-4" aria-hidden="true" />
      </Button>
    );
  }

  return (
    <Button
      type="button"
      variant="outline"
      size="sm"
      className={cn("text-muted-foreground h-8 justify-start gap-2 px-2", className)}
      onClick={openPalette}
    >
      <span className="bg-muted text-muted-foreground inline-flex h-5 w-5 items-center justify-center rounded-md text-[11px]">
        /
      </span>
      <span className="hidden sm:inline">Search</span>
      <kbd className="bg-muted text-muted-foreground ml-auto hidden items-center gap-1 rounded-md px-2 py-0.5 text-[10px] font-medium sm:inline-flex">
        {platformShortcut}
      </kbd>
    </Button>
  );
}
