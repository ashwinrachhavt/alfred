"use client";

import { useCallback, useEffect, useState } from "react";
import { usePathname } from "next/navigation";
import { Plus } from "lucide-react";
import { CaptureModal } from "./capture-modal";

export function CaptureButton() {
  const [open, setOpen] = useState(false);
  const pathname = usePathname();
  const isNotesPage = pathname === "/notes";

  // Global keyboard shortcut: Cmd+Shift+K
  const handleKeyDown = useCallback((e: KeyboardEvent) => {
    if ((e.metaKey || e.ctrlKey) && e.shiftKey && e.key.toLowerCase() === "k") {
      e.preventDefault();
      setOpen(true);
    }
  }, []);

  useEffect(() => {
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [handleKeyDown]);

  return (
    <>
      {/* Floating action button */}
      <button
        onClick={() => setOpen(true)}
        className={isNotesPage
          ? "fixed right-6 bottom-6 z-40 flex size-10 items-center justify-center rounded-sm border border-[var(--alfred-ruled-line)] bg-card/90 text-primary shadow-sm backdrop-blur transition-all hover:border-primary/40 hover:bg-card active:scale-95"
          : "fixed right-6 bottom-6 z-40 flex size-12 items-center justify-center rounded-full bg-primary text-primary-foreground shadow-lg transition-all hover:scale-105 hover:shadow-xl active:scale-95"
        }
        aria-label="Quick Capture"
        title="Quick Capture (⌘⇧K)"
      >
        <Plus className={isNotesPage ? "size-4" : "size-5"} />
      </button>

      <CaptureModal open={open} onOpenChange={setOpen} />
    </>
  );
}
