"use client";

import { useRouter } from "next/navigation";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { useCreateBlockNote } from "@blocknote/react";
import { BlockNoteView } from "@blocknote/shadcn";
import "@blocknote/shadcn/style.css";

import {
  Archive,
  ChevronLeft,
  Copy,
  Loader2,
  PanelRightClose,
  PanelRightOpen,
  Pin,
  PinOff,
} from "lucide-react";
import { toast } from "sonner";

import {
  useArchiveThinkingSession,
  useForkThinkingSession,
  useUpdateThinkingSession,
} from "@/features/thinking/mutations";
import { useThinkingSession } from "@/features/thinking/queries";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { cn } from "@/lib/utils";

// ---------------------------------------------------------------------------
// Autosave state
// ---------------------------------------------------------------------------

type AutosaveState = "idle" | "dirty" | "saving" | "saved" | "error";

function formatAutosaveLabel(state: AutosaveState): string {
  if (state === "saving") return "Saving...";
  if (state === "saved") return "Saved";
  if (state === "error") return "Save failed";
  if (state === "dirty") return "Unsaved";
  return "\u00A0";
}

// ---------------------------------------------------------------------------
// BlockNote Editor Wrapper
// ---------------------------------------------------------------------------

function BlockNoteEditor({
  initialContent,
  onChange,
}: {
  initialContent: unknown[] | undefined;
  onChange: (blocks: unknown[]) => void;
}) {
  const editor = useCreateBlockNote({
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    initialContent: initialContent as any,
  });

  return (
    <BlockNoteView
      editor={editor}
      onChange={() => {
        onChange(editor.document as unknown as unknown[]);
      }}
      theme="light"
      className="min-h-0 flex-1"
    />
  );
}

// ---------------------------------------------------------------------------
// Session Editor
// ---------------------------------------------------------------------------

export function SessionEditor({
  sessionId,
  onToggleDecompose,
  showDecompose,
}: {
  sessionId: number;
  onToggleDecompose: () => void;
  showDecompose: boolean;
}) {
  const router = useRouter();
  const sessionQuery = useThinkingSession(sessionId);
  const updateMutation = useUpdateThinkingSession(sessionId);
  const archiveMutation = useArchiveThinkingSession();
  const forkMutation = useForkThinkingSession();

  const [title, setTitle] = useState("");
  const [autosaveState, setAutosaveState] = useState<AutosaveState>("idle");

  const draftRef = useRef<{ title: string; blocks: unknown[] }>({
    title: "",
    blocks: [],
  });
  const lastSavedRef = useRef<{ title: string; blocksJson: string }>({
    title: "",
    blocksJson: "[]",
  });
  const debounceTimerRef = useRef<number | null>(null);
  const queuedSaveRef = useRef(false);

  // Hydrate from query data
  const session = sessionQuery.data;
  const initialBlocks = useMemo(() => {
    if (!session) return undefined;
    // blocks column stores BlockNote native JSON
    const raw = session.blocks;
    if (Array.isArray(raw) && raw.length > 0) return raw as unknown[];
    return undefined;
  }, [session]);

  useEffect(() => {
    if (!session) return;
    const t = session.title ?? "";
    setTitle(t);
    draftRef.current.title = t;
    const blocks = Array.isArray(session.blocks) ? session.blocks : [];
    draftRef.current.blocks = blocks as unknown[];
    lastSavedRef.current = {
      title: t,
      blocksJson: JSON.stringify(blocks),
    };
    setAutosaveState("idle");
  }, [session]);

  // Save logic
  const saveNow = useCallback(async () => {
    const current = draftRef.current;
    const currentBlocksJson = JSON.stringify(current.blocks);
    if (
      current.title === lastSavedRef.current.title &&
      currentBlocksJson === lastSavedRef.current.blocksJson
    ) {
      setAutosaveState("idle");
      return;
    }

    if (updateMutation.isPending) {
      queuedSaveRef.current = true;
      return;
    }

    setAutosaveState("saving");
    try {
      await updateMutation.mutateAsync({
        title: current.title.trim() || null,
        blocks: current.blocks,
      });
      lastSavedRef.current = {
        title: current.title,
        blocksJson: currentBlocksJson,
      };
      setAutosaveState("saved");
    } catch {
      setAutosaveState("error");
      toast.error("Failed to save session.");
    } finally {
      if (queuedSaveRef.current) {
        queuedSaveRef.current = false;
        void saveNow();
      }
    }
  }, [updateMutation]);

  const queueSave = useCallback(() => {
    setAutosaveState("dirty");
    if (debounceTimerRef.current) {
      window.clearTimeout(debounceTimerRef.current);
    }
    debounceTimerRef.current = window.setTimeout(() => {
      void saveNow();
    }, 3_000);
  }, [saveNow]);

  // Cleanup timer
  useEffect(() => {
    return () => {
      if (debounceTimerRef.current) window.clearTimeout(debounceTimerRef.current);
    };
  }, []);

  // Save on tab hide
  useEffect(() => {
    const onVisibilityChange = () => {
      if (document.visibilityState !== "hidden") return;
      void saveNow();
    };
    window.addEventListener("visibilitychange", onVisibilityChange);
    return () => window.removeEventListener("visibilitychange", onVisibilityChange);
  }, [saveNow]);

  // Actions
  const handleArchive = async () => {
    try {
      await archiveMutation.mutateAsync(sessionId);
      toast.success("Session archived.");
      router.push("/think");
    } catch {
      toast.error("Failed to archive session.");
    }
  };

  const handleFork = async () => {
    try {
      const forked = await forkMutation.mutateAsync(sessionId);
      toast.success("Session forked.");
      router.push(`/think/${forked.id}`);
    } catch {
      toast.error("Failed to fork session.");
    }
  };

  const handleTogglePin = async () => {
    if (!session) return;
    try {
      await updateMutation.mutateAsync({ pinned: !session.pinned });
    } catch {
      toast.error("Failed to update pin.");
    }
  };

  // Loading state
  if (sessionQuery.isLoading) {
    return (
      <div className="flex h-full flex-col p-6">
        <div className="space-y-3">
          <Skeleton className="h-9 w-1/2" />
          <Skeleton className="h-7 w-1/3" />
          <Skeleton className="h-64 w-full" />
        </div>
      </div>
    );
  }

  if (sessionQuery.isError) {
    return (
      <div className="flex h-full flex-col items-center justify-center p-6 text-center">
        <p className="text-muted-foreground text-sm">
          Failed to load session.{" "}
          <button
            type="button"
            className="text-primary underline underline-offset-2"
            onClick={() => sessionQuery.refetch()}
          >
            Retry
          </button>
        </p>
      </div>
    );
  }

  const statusLabel = formatAutosaveLabel(autosaveState);

  return (
    <div className="flex h-full flex-col">
      {/* Toolbar */}
      <header className="flex items-center justify-between gap-3 border-b px-6 py-3">
        <div className="flex min-w-0 flex-1 items-center gap-3">
          <Tooltip>
            <TooltipTrigger asChild>
              <Button
                type="button"
                size="icon"
                variant="ghost"
                className="h-8 w-8 shrink-0"
                onClick={() => router.push("/think")}
              >
                <ChevronLeft className="h-4 w-4" />
              </Button>
            </TooltipTrigger>
            <TooltipContent>Back to list</TooltipContent>
          </Tooltip>

          <input
            value={title}
            onChange={(e) => {
              const next = e.target.value;
              setTitle(next);
              draftRef.current.title = next;
              queueSave();
            }}
            onBlur={() => void saveNow()}
            className="min-w-0 flex-1 bg-transparent font-serif text-xl tracking-tight outline-none placeholder:text-[var(--alfred-text-tertiary)]"
            placeholder="Untitled session"
          />

          {session ? (
            <Badge
              variant="outline"
              className={cn(
                "shrink-0 text-[10px]",
                session.status === "draft" && "bg-yellow-500/10 text-yellow-700",
                session.status === "published" && "bg-green-500/10 text-green-700",
                session.status === "archived" && "bg-muted text-muted-foreground",
              )}
            >
              {session.status}
            </Badge>
          ) : null}
        </div>

        <div className="flex items-center gap-1">
          <span
            className={cn(
              "mr-2 font-mono text-[10px] uppercase tracking-widest",
              autosaveState === "saved" && "text-green-600",
              autosaveState === "error" && "text-red-600",
              autosaveState === "dirty" && "text-yellow-600",
              (autosaveState === "saving" || autosaveState === "idle") &&
                "text-muted-foreground",
            )}
          >
            {statusLabel}
          </span>

          <Tooltip>
            <TooltipTrigger asChild>
              <Button
                type="button"
                size="icon"
                variant="ghost"
                className="h-8 w-8"
                onClick={handleTogglePin}
              >
                {session?.pinned ? (
                  <PinOff className="h-4 w-4" />
                ) : (
                  <Pin className="h-4 w-4" />
                )}
              </Button>
            </TooltipTrigger>
            <TooltipContent>{session?.pinned ? "Unpin" : "Pin"}</TooltipContent>
          </Tooltip>

          <Tooltip>
            <TooltipTrigger asChild>
              <Button
                type="button"
                size="icon"
                variant="ghost"
                className="h-8 w-8"
                onClick={handleFork}
                disabled={forkMutation.isPending}
              >
                {forkMutation.isPending ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <Copy className="h-4 w-4" />
                )}
              </Button>
            </TooltipTrigger>
            <TooltipContent>Fork session</TooltipContent>
          </Tooltip>

          <Tooltip>
            <TooltipTrigger asChild>
              <Button
                type="button"
                size="icon"
                variant="ghost"
                className="h-8 w-8"
                onClick={handleArchive}
                disabled={archiveMutation.isPending}
              >
                {archiveMutation.isPending ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <Archive className="h-4 w-4" />
                )}
              </Button>
            </TooltipTrigger>
            <TooltipContent>Archive</TooltipContent>
          </Tooltip>

          <Tooltip>
            <TooltipTrigger asChild>
              <Button
                type="button"
                size="icon"
                variant="ghost"
                className="h-8 w-8"
                onClick={onToggleDecompose}
              >
                {showDecompose ? (
                  <PanelRightClose className="h-4 w-4" />
                ) : (
                  <PanelRightOpen className="h-4 w-4" />
                )}
              </Button>
            </TooltipTrigger>
            <TooltipContent>
              {showDecompose ? "Hide decompose" : "Show decompose"}
            </TooltipContent>
          </Tooltip>
        </div>
      </header>

      {/* Editor area */}
      <div className="min-h-0 flex-1 overflow-y-auto px-6 py-4">
        <div className="mx-auto max-w-3xl">
          {initialBlocks !== undefined || session ? (
            <BlockNoteEditor
              key={sessionId}
              initialContent={initialBlocks}
              onChange={(blocks) => {
                draftRef.current.blocks = blocks;
                queueSave();
              }}
            />
          ) : null}
        </div>
      </div>
    </div>
  );
}
