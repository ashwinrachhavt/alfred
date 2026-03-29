"use client";

import * as React from "react";

import { Check, Moon, Palette, Sun } from "lucide-react";
import { useTheme } from "next-themes";

import { Button } from "@/components/ui/button";
import {
 DropdownMenu,
 DropdownMenuContent,
 DropdownMenuLabel,
 DropdownMenuSeparator,
 DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { cn } from "@/lib/utils";
import { useAccentTheme, ACCENT_THEMES, type AccentThemeId } from "@/lib/hooks/use-accent-theme";

export function ThemePicker() {
 const { resolvedTheme, setTheme } = useTheme();
 const { accent, setAccent } = useAccentTheme();
 const [mounted, setMounted] = React.useState(false);

 React.useEffect(() => setMounted(true), []);

 const isDark = mounted ? resolvedTheme === "dark" : true;

 return (
 <DropdownMenu>
 <DropdownMenuTrigger asChild>
 <Button
 type="button"
 variant="ghost"
 size="icon"
 aria-label="Theme settings"
 >
 <Palette className="size-4" />
 </Button>
 </DropdownMenuTrigger>
 <DropdownMenuContent align="end" className="w-[220px]">
 {/* Mode toggle */}
 <DropdownMenuLabel className="font-medium text-[9px] uppercase tracking-widest text-[var(--alfred-text-tertiary)]">
 Mode
 </DropdownMenuLabel>
 <div className="flex gap-1 p-1">
 <button
 onClick={() => setTheme("light")}
 className={cn(
 "flex flex-1 items-center justify-center gap-1.5 rounded-md px-3 py-1.5 text-[11px] uppercase tracking-wider transition-colors",
 !isDark
 ? "bg-[var(--alfred-accent-muted)] text-primary"
 : "text-muted-foreground hover:text-foreground",
 )}
 >
 <Sun className="size-3" />
 Light
 </button>
 <button
 onClick={() => setTheme("dark")}
 className={cn(
 "flex flex-1 items-center justify-center gap-1.5 rounded-md px-3 py-1.5 text-[11px] uppercase tracking-wider transition-colors",
 isDark
 ? "bg-[var(--alfred-accent-muted)] text-primary"
 : "text-muted-foreground hover:text-foreground",
 )}
 >
 <Moon className="size-3" />
 Dark
 </button>
 </div>

 <DropdownMenuSeparator />

 {/* Accent color */}
 <DropdownMenuLabel className="font-medium text-[9px] uppercase tracking-widest text-[var(--alfred-text-tertiary)]">
 Accent
 </DropdownMenuLabel>
 <div className="grid grid-cols-3 gap-1.5 p-2">
 {ACCENT_THEMES.map((theme) => (
 <button
 key={theme.id}
 onClick={() => setAccent(theme.id as AccentThemeId)}
 className={cn(
 "group relative flex flex-col items-center gap-1 rounded-md p-2 transition-colors hover:bg-[var(--alfred-accent-subtle)]",
 accent === theme.id && "bg-[var(--alfred-accent-subtle)]",
 )}
 aria-label={`${theme.label} accent`}
 >
 <div
 className="relative size-6 rounded-full border border-[var(--border)]"
 style={{ backgroundColor: theme.color }}
 >
 {accent === theme.id && (
 <Check className="absolute inset-0 m-auto size-3 text-white" />
 )}
 </div>
 <span className="text-[8px] uppercase tracking-wider text-muted-foreground">
 {theme.label}
 </span>
 </button>
 ))}
 </div>
 </DropdownMenuContent>
 </DropdownMenu>
 );
}
