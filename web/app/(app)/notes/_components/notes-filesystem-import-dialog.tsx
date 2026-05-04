"use client";

import { useEffect, useMemo, useRef, useState, type ChangeEvent, type FormEvent } from "react";
import {
  ArrowUp,
  Download,
  FileText,
  Folder,
  FolderOpen,
  Home,
  LoaderCircle,
  RefreshCcw,
  Upload,
} from "lucide-react";
import { toast } from "sonner";

import { EmptyState } from "@/components/ui/empty-state";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import {
  useImportNoteFilesystem,
  useImportUploadedNoteFilesystem,
} from "@/features/notes/mutations";
import { useNoteFilesystemBrowse } from "@/features/notes/queries";
import { ApiError } from "@/lib/api/client";

type NotesFilesystemImportDialogProps = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  workspaceId: string | null;
  onImported: (noteId: string) => void;
};

function describeImportResult(importedCount: number, skippedCount: number): string {
  if (skippedCount > 0) {
    return `Imported ${importedCount} notes, skipped ${skippedCount}.`;
  }
  return `Imported ${importedCount} notes.`;
}

export function NotesFilesystemImportDialog({
  open,
  onOpenChange,
  workspaceId,
  onImported,
}: NotesFilesystemImportDialogProps) {
  const [browserPath, setBrowserPath] = useState<string | null>(null);
  const [pathInput, setPathInput] = useState("");
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const folderInputRef = useRef<HTMLInputElement | null>(null);

  const browseQuery = useNoteFilesystemBrowse(browserPath, open);
  const importMutation = useImportNoteFilesystem({ workspaceId });
  const uploadMutation = useImportUploadedNoteFilesystem({ workspaceId });

  const currentPath = browseQuery.data?.path ?? pathInput.trim();
  const currentEntries = useMemo(() => browseQuery.data?.items ?? [], [browseQuery.data?.items]);
  const isImporting = importMutation.isPending || uploadMutation.isPending;

  useEffect(() => {
    const folderInput = folderInputRef.current;
    if (!folderInput) return;
    folderInput.setAttribute("webkitdirectory", "");
    folderInput.setAttribute("directory", "");
  }, []);

  async function handleImport(path: string) {
    if (!workspaceId) {
      toast.error("Create or load a workspace before importing.");
      return;
    }

    try {
      const result = await importMutation.mutateAsync({
        workspace_id: workspaceId,
        path,
      });
      toast.success(describeImportResult(result.imported_count, result.skipped_count));
      onImported(result.root_note_id);
      onOpenChange(false);
    } catch (error) {
      const message =
        error instanceof ApiError || error instanceof Error
          ? error.message
          : "Failed to import the selected path.";
      toast.error(message);
    }
  }

  async function handleUpload(files: FileList | null) {
    if (!workspaceId) {
      toast.error("Create or load a workspace before importing.");
      return;
    }

    const selectedFiles = Array.from(files ?? []);
    if (!selectedFiles.length) return;

    try {
      const result = await uploadMutation.mutateAsync({
        workspace_id: workspaceId,
        files: selectedFiles,
      });
      toast.success(describeImportResult(result.imported_count, result.skipped_count));
      onImported(result.root_note_id);
      onOpenChange(false);
    } catch (error) {
      const message =
        error instanceof ApiError || error instanceof Error
          ? error.message
          : "Failed to import the selected upload.";
      toast.error(message);
    }
  }

  function handleUploadChange(event: ChangeEvent<HTMLInputElement>) {
    const input = event.currentTarget;
    void handleUpload(input.files).finally(() => {
      input.value = "";
    });
  }

  function handleBrowseSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBrowserPath(pathInput.trim() || null);
  }

  return (
    <Dialog
      open={open}
      onOpenChange={(nextOpen) => {
        if (nextOpen) {
          setBrowserPath(null);
          setPathInput("");
        }
        onOpenChange(nextOpen);
      }}
    >
      <DialogContent className="sm:max-w-3xl">
        <DialogHeader>
          <DialogTitle>Import Files</DialogTitle>
          <DialogDescription>
            Upload UTF-8 text files from Finder, or paste a server-visible path and import it into
            Notes.
          </DialogDescription>
        </DialogHeader>

        <form onSubmit={handleBrowseSubmit} className="space-y-4">
          <input
            ref={fileInputRef}
            type="file"
            multiple
            className="hidden"
            onChange={handleUploadChange}
          />
          <input
            ref={folderInputRef}
            type="file"
            multiple
            className="hidden"
            onChange={handleUploadChange}
          />
          <div className="flex flex-wrap items-center gap-2">
            <Button
              type="button"
              disabled={!workspaceId || isImporting}
              onClick={() => fileInputRef.current?.click()}
            >
              {uploadMutation.isPending ? (
                <LoaderCircle className="mr-2 h-4 w-4 animate-spin" />
              ) : (
                <Upload className="mr-2 h-4 w-4" />
              )}
              Upload files
            </Button>
            <Button
              type="button"
              variant="outline"
              disabled={!workspaceId || isImporting}
              onClick={() => folderInputRef.current?.click()}
            >
              {uploadMutation.isPending ? (
                <LoaderCircle className="mr-2 h-4 w-4 animate-spin" />
              ) : (
                <FolderOpen className="mr-2 h-4 w-4" />
              )}
              Upload folder
            </Button>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <Button
              type="button"
              variant="outline"
              size="icon"
              onClick={() => {
                setBrowserPath(null);
                setPathInput("");
              }}
              disabled={browseQuery.isFetching || isImporting}
            >
              <Home className="h-4 w-4" />
              <span className="sr-only">Go to import root</span>
            </Button>
            <Button
              type="button"
              variant="outline"
              size="icon"
              onClick={() => {
                const nextPath = browseQuery.data?.parent_path ?? null;
                setBrowserPath(nextPath);
                setPathInput(nextPath ?? "");
              }}
              disabled={!browseQuery.data?.parent_path || browseQuery.isFetching || isImporting}
            >
              <ArrowUp className="h-4 w-4" />
              <span className="sr-only">Go up</span>
            </Button>
            <Button
              type="button"
              variant="outline"
              size="icon"
              onClick={() => void browseQuery.refetch()}
              disabled={browseQuery.isFetching || isImporting}
            >
              <RefreshCcw className="h-4 w-4" />
              <span className="sr-only">Refresh</span>
            </Button>
            <Input
              value={pathInput}
              onChange={(event) => setPathInput(event.target.value)}
              placeholder="/app/data/notes or ~/notes/draft.md"
              className="min-w-[280px] flex-1"
            />
            <Button type="submit" variant="outline" disabled={browseQuery.isFetching || isImporting}>
              {browseQuery.isFetching ? (
                <LoaderCircle className="mr-2 h-4 w-4 animate-spin" />
              ) : (
                <FolderOpen className="mr-2 h-4 w-4" />
              )}
              Browse folder
            </Button>
            <Button
              type="button"
              disabled={!pathInput.trim() || isImporting || !workspaceId}
              onClick={() => void handleImport(pathInput.trim())}
            >
              {importMutation.isPending && importMutation.variables?.path === pathInput.trim() ? (
                <LoaderCircle className="mr-2 h-4 w-4 animate-spin" />
              ) : (
                <Download className="mr-2 h-4 w-4" />
              )}
              Import path
            </Button>
          </div>

          <div className="bg-muted/30 flex items-center justify-between gap-3 rounded-lg border px-3 py-2">
            <div className="min-w-0">
              <p className="text-xs tracking-[0.2em] text-[var(--alfred-text-tertiary)] uppercase">
                Current path
              </p>
              <p className="truncate text-sm">
                {browseQuery.data?.path ?? "Loading import root..."}
              </p>
            </div>
            <Button
              type="button"
              onClick={() => void handleImport(currentPath)}
              disabled={!currentPath || isImporting || !workspaceId}
              className="shrink-0"
            >
              {importMutation.isPending ? (
                <LoaderCircle className="mr-2 h-4 w-4 animate-spin" />
              ) : (
                <Download className="mr-2 h-4 w-4" />
              )}
              Import current path
            </Button>
          </div>

          <div className="bg-card max-h-[420px] overflow-y-auto rounded-xl border">
            {browseQuery.isPending ? (
              <div className="text-muted-foreground flex items-center justify-center py-12 text-sm">
                <LoaderCircle className="mr-2 h-4 w-4 animate-spin" />
                Loading directory…
              </div>
            ) : browseQuery.isError ? (
              <EmptyState
                title="Unable to browse this path"
                description={
                  browseQuery.error instanceof Error
                    ? browseQuery.error.message
                    : "The selected path could not be loaded."
                }
                action={
                  <Button
                    type="button"
                    variant="outline"
                    onClick={() => void browseQuery.refetch()}
                  >
                    Try again
                  </Button>
                }
                className="py-12"
              />
            ) : currentEntries.length ? (
              <ul className="divide-y">
                {currentEntries.map((entry) => {
                  const isDirectory = entry.kind === "directory";
                  const isImportingPath =
                    importMutation.isPending && importMutation.variables?.path === entry.path;

                  return (
                    <li key={entry.path} className="flex items-center gap-3 px-3 py-2.5">
                      <button
                        type="button"
                        className={`flex min-w-0 flex-1 items-center gap-3 text-left ${
                          isDirectory ? "hover:text-foreground" : "cursor-default"
                        }`}
                        onClick={() => {
                          if (isDirectory) {
                            setBrowserPath(entry.path);
                            setPathInput(entry.path);
                          }
                        }}
                        disabled={!isDirectory}
                      >
                        <span className="bg-muted text-muted-foreground rounded-md p-1.5">
                          {isDirectory ? (
                            <Folder className="h-4 w-4" />
                          ) : (
                            <FileText className="h-4 w-4" />
                          )}
                        </span>
                        <div className="min-w-0 flex-1">
                          <p className="truncate text-sm">{entry.name}</p>
                          <p className="text-muted-foreground truncate text-xs">
                            {entry.reason
                              ? entry.reason
                              : entry.size_bytes
                                ? `${Math.max(1, Math.round(entry.size_bytes / 1024))} KB`
                                : isDirectory
                                  ? "Folder"
                                  : "Text file"}
                          </p>
                        </div>
                      </button>

                      <Badge variant="secondary" className="shrink-0">
                        {entry.kind}
                      </Badge>

                      <Button
                        type="button"
                        variant={entry.importable ? "outline" : "ghost"}
                        className="shrink-0"
                        disabled={!entry.importable || isImporting || !workspaceId}
                        onClick={() => void handleImport(entry.path)}
                      >
                        {isImportingPath ? (
                          <LoaderCircle className="mr-2 h-4 w-4 animate-spin" />
                        ) : (
                          <Download className="mr-2 h-4 w-4" />
                        )}
                        Import
                      </Button>
                    </li>
                  );
                })}
              </ul>
            ) : (
              <EmptyState
                title="This folder is empty"
                description="Choose another path with importable text files."
                className="py-12"
              />
            )}
          </div>
        </form>

        <DialogFooter>
          <Button type="button" variant="ghost" onClick={() => onOpenChange(false)}>
            Close
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
