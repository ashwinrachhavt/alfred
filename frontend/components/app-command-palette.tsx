"use client";

import * as React from "react";
import { useRouter } from "next/navigation";
import { useTheme } from "next-themes";
import { ListChecks, Moon, Search, Sun } from "lucide-react";

import { appNavItems } from "@/lib/navigation";
import { cn } from "@/lib/utils";
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
  return typeof navigator !== "undefined" && /Mac|iPhone|iPad|iPod/i.test(navigator.platform)
    ? "⌘K"
    : "Ctrl K";
}

function useThemeToggleShortcut(): string {
  return typeof navigator !== "undefined" && /Mac|iPhone|iPad|iPod/i.test(navigator.platform)
    ? "⌘⇧L"
    : "Ctrl Shift L";
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
  const { activeCount, setTaskCenterOpen } = useTaskTracker();
  const platformShortcut = usePlatformShortcut();
  const themeShortcut = useThemeToggleShortcut();
  const [query, setQuery] = React.useState("");

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

  return (
    <CommandDialog open={open} onOpenChange={onOpenChange} contentClassName="max-w-xl">
      <CommandInput placeholder="Search Alfred…" value={query} onValueChange={setQuery} autoFocus />
      <CommandList>
        <CommandEmpty>No matches.</CommandEmpty>

        <CommandGroup heading="Navigate">
          {appNavItems.map((item) => (
            <CommandItem
              key={item.key}
              value={[item.title, item.href, ...item.keywords].join(" ")}
              onSelect={() => navigateTo(item.href)}
            >
              <item.icon className="h-4 w-4" aria-hidden="true" />
              <span>{item.title}</span>
            </CommandItem>
          ))}
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
