"use client";

import { useEffect, useMemo, useState } from "react";
import { Loader2 } from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import type {
  ResearchAgentSpec,
  ResearchAgentSpecCreate,
  SubAgentSpec,
  ToolCatalogEntry,
} from "@/lib/api/research-agents";
import {
  useCreateResearchAgent,
  useUpdateResearchAgent,
} from "@/features/research-agents/queries";

import { SubAgentEditor } from "./subagent-editor";
import { ToolPicker } from "./tool-picker";

type Mode =
  | { kind: "create"; prefill?: ResearchAgentSpec }
  | { kind: "edit"; spec: ResearchAgentSpec };

type Props = {
  mode: Mode;
  catalog: ToolCatalogEntry[];
  onDone: () => void;
};

type DraftState = Omit<ResearchAgentSpecCreate, "subagents"> & {
  subagents: SubAgentSpec[];
};

const EMPTY_DRAFT: DraftState = {
  slug: "",
  name: "",
  description: "",
  instructions: "",
  model_name: null,
  tool_allowlist: [],
  connector_bindings: {},
  subagents: [],
};

function slugify(input: string): string {
  return input
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-|-$/g, "");
}

function specToDraft(spec: ResearchAgentSpec): DraftState {
  return {
    slug: spec.slug,
    name: spec.name,
    description: spec.description,
    instructions: spec.instructions,
    model_name: spec.model_name,
    tool_allowlist: [...spec.tool_allowlist],
    connector_bindings: { ...spec.connector_bindings },
    subagents: spec.subagents.map((sa) => ({ ...sa, tools: [...sa.tools] })),
  };
}

export function AgentEditorForm({ mode, catalog, onDone }: Props) {
  const isEdit = mode.kind === "edit";
  const isSystem = isEdit && mode.spec.is_system;

  const initialDraft: DraftState = isEdit
    ? specToDraft(mode.spec)
    : mode.prefill
      ? specToDraft(mode.prefill)
      : EMPTY_DRAFT;

  const [draft, setDraft] = useState<DraftState>(initialDraft);
  const [slugTouched, setSlugTouched] = useState(isEdit || Boolean(!isEdit && mode.kind === "create" && mode.prefill));

  const createMut = useCreateResearchAgent();
  const updateMut = useUpdateResearchAgent();

  // Auto-derive slug from name during create (until the user overrides).
  useEffect(() => {
    if (!isEdit && !slugTouched) {
      setDraft((d) => ({ ...d, slug: slugify(d.name) }));
    }
  }, [draft.name, slugTouched, isEdit]);

  const valid = useMemo(() => {
    if (!draft.name.trim()) return false;
    if (!draft.slug.trim()) return false;
    if (!draft.instructions.trim()) return false;
    for (const sa of draft.subagents) {
      if (!sa.name.trim() || !sa.description.trim() || !sa.system_prompt.trim()) {
        return false;
      }
    }
    return true;
  }, [draft]);

  const toggleTool = (tool: string, checked: boolean) => {
    setDraft((d) => ({
      ...d,
      tool_allowlist: checked
        ? [...d.tool_allowlist, tool]
        : d.tool_allowlist.filter((t) => t !== tool),
    }));
  };

  const onSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!valid) {
      toast.error("Fill in name, slug, instructions, and all sub-agent fields.");
      return;
    }
    try {
      if (isEdit) {
        await updateMut.mutateAsync({
          id: mode.spec.id,
          body: {
            name: draft.name,
            description: draft.description,
            instructions: draft.instructions,
            model_name: draft.model_name,
            tool_allowlist: draft.tool_allowlist,
            connector_bindings: draft.connector_bindings,
            subagents: draft.subagents,
          },
        });
        toast.success(`Updated ${draft.name}`);
      } else {
        await createMut.mutateAsync({
          slug: draft.slug,
          name: draft.name,
          description: draft.description,
          instructions: draft.instructions,
          model_name: draft.model_name,
          tool_allowlist: draft.tool_allowlist,
          connector_bindings: draft.connector_bindings,
          subagents: draft.subagents,
        });
        toast.success(`Created ${draft.name}`);
      }
      onDone();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Save failed");
    }
  };

  const busy = createMut.isPending || updateMut.isPending;

  return (
    <form onSubmit={onSubmit} className="space-y-5">
      {isSystem ? (
        <div className="border-border/60 bg-muted/30 rounded-md border px-3 py-2 text-xs">
          This is a system agent and cannot be edited. Duplicate it to make your own
          version.
        </div>
      ) : null}

      <fieldset disabled={isSystem} className="space-y-5">
        <div className="grid grid-cols-1 gap-3 md:grid-cols-[2fr_1fr]">
          <div className="space-y-1.5">
            <Label htmlFor="agent-name" className="text-xs">
              Name
            </Label>
            <Input
              id="agent-name"
              value={draft.name}
              onChange={(e) => setDraft((d) => ({ ...d, name: e.target.value }))}
              placeholder="Academic Literature Review"
              className="h-9"
            />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="agent-slug" className="text-xs">
              Slug
            </Label>
            <Input
              id="agent-slug"
              value={draft.slug}
              onChange={(e) => {
                setSlugTouched(true);
                setDraft((d) => ({ ...d, slug: slugify(e.target.value) }));
              }}
              placeholder="academic-literature-review"
              className="h-9 font-mono text-xs"
              disabled={isEdit}
            />
          </div>
        </div>

        <div className="space-y-1.5">
          <Label htmlFor="agent-description" className="text-xs">
            Description
          </Label>
          <Input
            id="agent-description"
            value={draft.description}
            onChange={(e) => setDraft((d) => ({ ...d, description: e.target.value }))}
            placeholder="One-line description shown in the agent picker"
            className="h-9"
          />
        </div>

        <div className="space-y-1.5">
          <Label htmlFor="agent-model" className="text-xs">
            Model (optional)
          </Label>
          <Input
            id="agent-model"
            value={draft.model_name ?? ""}
            onChange={(e) =>
              setDraft((d) => ({ ...d, model_name: e.target.value.trim() || null }))
            }
            placeholder="openai:gpt-5.2 (leave empty to use the default)"
            className="h-9 font-mono text-xs"
          />
        </div>

        <div className="space-y-1.5">
          <Label htmlFor="agent-instructions" className="text-xs">
            Orchestrator instructions
          </Label>
          <Textarea
            id="agent-instructions"
            value={draft.instructions}
            onChange={(e) => setDraft((d) => ({ ...d, instructions: e.target.value }))}
            placeholder="You are a research orchestrator. For each request: 1. plan todos, 2. delegate to sub-agents, 3. synthesize."
            rows={6}
            className="text-xs"
          />
        </div>

        <ToolPicker
          catalog={catalog}
          selected={draft.tool_allowlist}
          onToggle={toggleTool}
          label="Orchestrator tools"
          helpText="Tools the main orchestrator agent can call directly. Usually kept small — delegate heavy work to sub-agents."
        />

        <SubAgentEditor
          subagents={draft.subagents}
          catalog={catalog}
          onChange={(next) => setDraft((d) => ({ ...d, subagents: next }))}
        />
      </fieldset>

      <div className="border-border/60 flex items-center justify-end gap-2 border-t pt-4">
        <Button type="button" variant="ghost" size="sm" onClick={onDone} disabled={busy}>
          Cancel
        </Button>
        {!isSystem ? (
          <Button type="submit" size="sm" disabled={!valid || busy}>
            {busy ? (
              <>
                <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" />
                Saving...
              </>
            ) : isEdit ? (
              "Save changes"
            ) : (
              "Create agent"
            )}
          </Button>
        ) : null}
      </div>
    </form>
  );
}
