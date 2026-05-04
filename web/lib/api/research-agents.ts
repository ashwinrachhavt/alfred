import { apiFetch } from "@/lib/api/client";
import { apiRoutes } from "@/lib/api/routes";

// Mirrors Pydantic SubAgentSpec
export type SubAgentSpec = {
  name: string;
  description: string;
  system_prompt: string;
  tools: string[];
  model?: string | null;
};

export type ResearchAgentSpec = {
  id: number;
  slug: string;
  name: string;
  description: string;
  instructions: string;
  model_name: string | null;
  tool_allowlist: string[];
  connector_bindings: Record<string, unknown>;
  subagents: SubAgentSpec[];
  is_system: boolean;
  owner_id: string | null;
};

export type ResearchAgentSpecCreate = Omit<
  ResearchAgentSpec,
  "id" | "is_system" | "owner_id"
>;

export type ResearchAgentSpecUpdate = Partial<
  Omit<ResearchAgentSpec, "id" | "slug" | "is_system" | "owner_id">
>;

export type ToolCatalogEntry = {
  name: string;
  description: string;
  requires_connector: string | null;
  category: string;
};

export async function listResearchAgents(): Promise<ResearchAgentSpec[]> {
  return apiFetch<ResearchAgentSpec[]>(apiRoutes.research.agents, { cache: "no-store" });
}

export async function getResearchAgent(id: number): Promise<ResearchAgentSpec> {
  return apiFetch<ResearchAgentSpec>(apiRoutes.research.agentById(id), { cache: "no-store" });
}

export async function createResearchAgent(
  body: ResearchAgentSpecCreate,
): Promise<ResearchAgentSpec> {
  return apiFetch<ResearchAgentSpec>(apiRoutes.research.agents, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

export async function updateResearchAgent(
  id: number,
  body: ResearchAgentSpecUpdate,
): Promise<ResearchAgentSpec> {
  return apiFetch<ResearchAgentSpec>(apiRoutes.research.agentById(id), {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

export async function deleteResearchAgent(id: number): Promise<void> {
  await apiFetch<{ ok: boolean }>(apiRoutes.research.agentById(id), {
    method: "DELETE",
  });
}

export async function getToolCatalog(): Promise<ToolCatalogEntry[]> {
  return apiFetch<ToolCatalogEntry[]>(apiRoutes.research.agentsCatalog, { cache: "no-store" });
}
