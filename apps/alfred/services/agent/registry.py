"""Central registry for Alfred agent specs."""

from __future__ import annotations

from alfred.services.agent.agent_types import AGENT_TYPES
from alfred.services.agent.harness import AgentSpec


def _specialist_specs() -> dict[str, AgentSpec]:
    return {
        name: AgentSpec(
            name=agent_type.name,
            description=agent_type.description,
            system_prompt=agent_type.system_prompt,
            tool_names=tuple(agent_type.tool_names),
            max_iterations=agent_type.max_iterations,
            prompt_version=f"{agent_type.name}:v1",
            risk_profile="networked" if agent_type.name in {"research", "connector"} else "standard",
        )
        for name, agent_type in AGENT_TYPES.items()
    }


AGENT_SPECS: dict[str, AgentSpec] = {
    "chat": AgentSpec(
        name="chat",
        description="Main Alfred chat agent with broad delegated tool access.",
        system_prompt="Built dynamically by SystemPromptBuilder.",
        max_iterations=10,
        supports_streaming=True,
        prompt_version="chat:v1",
        risk_profile="standard",
    ),
    "digest": AgentSpec(
        name="digest",
        description="Reflect-stage agent that writes a grounded daily digest.",
        system_prompt="See DigestAgent._SYSTEM_PROMPT.",
        max_iterations=1,
        prompt_version="digest:v1",
        risk_profile="read_only",
    ),
    "carryover": AgentSpec(
        name="carryover",
        description="Deterministic prep-stage agent that carries open todos forward.",
        system_prompt="Deterministic non-LLM pipeline step.",
        max_iterations=0,
        prompt_version="carryover:v1",
        risk_profile="writer",
        artifact_policy="off",
    ),
    "agentic_rag": AgentSpec(
        name="agentic_rag",
        description="LangGraph RAG agent for answering from retrieved documents.",
        system_prompt="LangGraph nodes own prompting.",
        max_iterations=10,
        prompt_version="agentic_rag:v1",
        risk_profile="read_only",
    ),
    **_specialist_specs(),
}


def get_agent_spec(name: str) -> AgentSpec:
    try:
        return AGENT_SPECS[name]
    except KeyError as exc:
        raise ValueError(f"Unknown agent spec: {name}") from exc


__all__ = ["AGENT_SPECS", "get_agent_spec"]
