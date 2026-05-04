"use client";

import { useMemo, useState } from "react";
import {
  ArrowLeft,
  Copy,
  Lock,
  Pencil,
  Plus,
  Trash2,
} from "lucide-react";
import Link from "next/link";
import { toast } from "sonner";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";
import { cn } from "@/lib/utils";
import type { ResearchAgentSpec } from "@/lib/api/research-agents";
import {
  useDeleteResearchAgent,
  useResearchAgents,
  useToolCatalog,
} from "@/features/research-agents/queries";

import { AgentEditorForm } from "./agent-editor-form";

type EditorMode =
  | { kind: "closed" }
  | { kind: "create"; prefill?: ResearchAgentSpec }
  | { kind: "edit"; spec: ResearchAgentSpec };

function AgentCard({
  spec,
  onEdit,
  onDuplicate,
  onDelete,
}: {
  spec: ResearchAgentSpec;
  onEdit: () => void;
  onDuplicate: () => void;
  onDelete: () => void;
}) {
  const subTools = new Set<string>();
  for (const sa of spec.subagents) {
    for (const t of sa.tools) subTools.add(t);
  }
  const totalTools = spec.tool_allowlist.length + subTools.size;

  return (
    <Card className="group transition-colors hover:border-primary/30">
      <CardHeader className="pb-2">
        <div className="flex items-start justify-between gap-2">
          <div className="min-w-0">
            <CardTitle className="flex items-center gap-2 text-base">
              <span className="truncate">{spec.name}</span>
              {spec.is_system ? (
                <Badge variant="outline" className="flex items-center gap-1 text-[10px]">
                  <Lock className="h-2.5 w-2.5" />
                  system
                </Badge>
              ) : null}
            </CardTitle>
            <p className="text-muted-foreground line-clamp-2 mt-0.5 text-xs">
              {spec.description || "No description"}
            </p>
          </div>
        </div>
      </CardHeader>
      <CardContent className="space-y-2 pt-0">
        <div className="flex flex-wrap gap-1">
          {spec.subagents.length > 0 ? (
            <Badge variant="secondary" className="text-[10px]">
              {spec.subagents.length} sub-agent{spec.subagents.length === 1 ? "" : "s"}
            </Badge>
          ) : null}
          {totalTools > 0 ? (
            <Badge variant="outline" className="text-[10px]">
              {totalTools} tool{totalTools === 1 ? "" : "s"}
            </Badge>
          ) : null}
          <Badge variant="outline" className="font-mono text-[10px]">
            {spec.slug}
          </Badge>
        </div>

        <div className="flex items-center gap-1 pt-1">
          <Button
            size="sm"
            variant="ghost"
            className="h-7 px-2 text-xs"
            onClick={onEdit}
          >
            <Pencil className="mr-1 h-3 w-3" />
            {spec.is_system ? "View" : "Edit"}
          </Button>
          <Button
            size="sm"
            variant="ghost"
            className="h-7 px-2 text-xs"
            onClick={onDuplicate}
          >
            <Copy className="mr-1 h-3 w-3" />
            Duplicate
          </Button>
          {!spec.is_system ? (
            <Button
              size="sm"
              variant="ghost"
              className="text-destructive hover:text-destructive ml-auto h-7 px-2 text-xs"
              onClick={onDelete}
            >
              <Trash2 className="mr-1 h-3 w-3" />
              Delete
            </Button>
          ) : null}
        </div>
      </CardContent>
    </Card>
  );
}

export function AgentsListClient() {
  const agentsQuery = useResearchAgents();
  const catalogQuery = useToolCatalog();
  const deleteMut = useDeleteResearchAgent();

  const [mode, setMode] = useState<EditorMode>({ kind: "closed" });
  const [confirmDelete, setConfirmDelete] = useState<ResearchAgentSpec | null>(null);

  const agents = agentsQuery.data ?? [];
  const catalog = catalogQuery.data ?? [];

  const { systemAgents, userAgents } = useMemo(
    () => ({
      systemAgents: agents.filter((a) => a.is_system),
      userAgents: agents.filter((a) => !a.is_system),
    }),
    [agents],
  );

  const handleDuplicate = (spec: ResearchAgentSpec) => {
    const copy: ResearchAgentSpec = {
      ...spec,
      id: -1,
      slug: `${spec.slug}-copy`,
      name: `${spec.name} (copy)`,
      is_system: false,
      owner_id: null,
      tool_allowlist: [...spec.tool_allowlist],
      connector_bindings: { ...spec.connector_bindings },
      subagents: spec.subagents.map((sa) => ({ ...sa, tools: [...sa.tools] })),
    };
    setMode({ kind: "create", prefill: copy });
  };

  const closeEditor = () => {
    setMode({ kind: "closed" });
  };

  const handleConfirmDelete = async () => {
    if (!confirmDelete) return;
    try {
      await deleteMut.mutateAsync(confirmDelete.id);
      toast.success(`Deleted ${confirmDelete.name}`);
      setConfirmDelete(null);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Delete failed");
    }
  };

  const sheetTitle =
    mode.kind === "edit" ? `${mode.spec.is_system ? "View" : "Edit"} agent` : "New research agent";

  return (
    <div className="mx-auto max-w-5xl space-y-8 px-6 py-8">
      {/* Header */}
      <div className="space-y-2">
        <Button variant="ghost" size="sm" asChild className="h-7 px-2">
          <Link href="/settings">
            <ArrowLeft className="mr-1 h-3 w-3" />
            Settings
          </Link>
        </Button>
        <div className="flex items-center justify-between">
          <div>
            <h1 className="font-serif text-3xl tracking-tight">Research Agents</h1>
            <p className="text-muted-foreground mt-1 font-mono text-xs uppercase tracking-widest">
              Define orchestrators, sub-agents, and tool allowlists
            </p>
          </div>
          <Button size="sm" onClick={() => setMode({ kind: "create" })}>
            <Plus className="mr-1.5 h-3.5 w-3.5" />
            New agent
          </Button>
        </div>
      </div>

      {/* User agents */}
      <section className="space-y-3">
        <h2 className="text-muted-foreground text-[11px] font-medium uppercase tracking-widest">
          Your agents
        </h2>
        {agentsQuery.isLoading ? (
          <p className="text-muted-foreground text-sm">Loading...</p>
        ) : userAgents.length === 0 ? (
          <p
            className={cn(
              "border-border/60 text-muted-foreground rounded-md border border-dashed px-4 py-6 text-center text-sm",
            )}
          >
            You haven&apos;t created any custom agents yet. Click New agent above, or duplicate a
            system agent below to start from a template.
          </p>
        ) : (
          <div className="grid gap-3 md:grid-cols-2">
            {userAgents.map((spec) => (
              <AgentCard
                key={spec.id}
                spec={spec}
                onEdit={() => setMode({ kind: "edit", spec })}
                onDuplicate={() => handleDuplicate(spec)}
                onDelete={() => setConfirmDelete(spec)}
              />
            ))}
          </div>
        )}
      </section>

      {/* System agents */}
      <section className="space-y-3">
        <h2 className="text-muted-foreground text-[11px] font-medium uppercase tracking-widest">
          Built-in agents
        </h2>
        <div className="grid gap-3 md:grid-cols-2">
          {systemAgents.map((spec) => (
            <AgentCard
              key={spec.id}
              spec={spec}
              onEdit={() => setMode({ kind: "edit", spec })}
              onDuplicate={() => handleDuplicate(spec)}
              onDelete={() => {}}
            />
          ))}
        </div>
      </section>

      {/* Editor sheet */}
      <Sheet open={mode.kind !== "closed"} onOpenChange={(o) => !o && closeEditor()}>
        <SheetContent side="right" className="w-full overflow-y-auto p-0 sm:max-w-xl">
          <SheetHeader className="sticky top-0 z-10 border-b border-border/60 bg-background px-6 py-4">
            <SheetTitle>{sheetTitle}</SheetTitle>
            <SheetDescription className="text-xs">
              {mode.kind === "edit" && mode.spec.is_system
                ? "Read-only view of a built-in agent. Use Duplicate to make your own editable copy."
                : "Define the orchestrator, its tools, and the sub-agents it can delegate to."}
            </SheetDescription>
          </SheetHeader>
          <div className="px-6 py-5">
            {mode.kind !== "closed" && catalog.length > 0 ? (
              <AgentEditorForm
                mode={
                  mode.kind === "edit"
                    ? { kind: "edit", spec: mode.spec }
                    : { kind: "create", prefill: mode.prefill }
                }
                catalog={catalog}
                onDone={closeEditor}
              />
            ) : (
              <p className="text-muted-foreground text-sm">Loading tool catalog...</p>
            )}
          </div>
        </SheetContent>
      </Sheet>

      {/* Delete confirm */}
      <Dialog open={confirmDelete !== null} onOpenChange={(o) => !o && setConfirmDelete(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Delete {confirmDelete?.name}?</DialogTitle>
            <DialogDescription>
              This removes the agent from your library. Existing run history is not affected.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="ghost" onClick={() => setConfirmDelete(null)} disabled={deleteMut.isPending}>
              Cancel
            </Button>
            <Button
              variant="destructive"
              onClick={handleConfirmDelete}
              disabled={deleteMut.isPending}
            >
              {deleteMut.isPending ? "Deleting..." : "Delete"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
