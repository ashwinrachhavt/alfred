from __future__ import annotations

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langgraph.graph import END, START, StateGraph

from alfred.agents.company_outreach.state import OutreachState
from alfred.agents.company_outreach.tools import CompanyResearchTool
from alfred.agents.utils.runtime import tools_node as run_tools_node
from alfred.prompts import load_prompt
from alfred.services.agentic_rag import create_retriever_tool, make_llm, make_retriever


def make_tools(*, k: int = 6):
    retriever = create_retriever_tool(
        make_retriever(k=k),
        name="profile_search",
        description=(
            "Search Ashwin's personal notes and resume for background, accomplishments, and skills. "
            "Use this before drafting outreach or tailoring the pitch."
        ),
    )
    return [retriever, CompanyResearchTool()]


OUTREACH_SYSTEM_PROMPT = load_prompt("company_outreach", "system.md")
_FINAL_PROMPT_TEMPLATE = load_prompt("company_outreach", "final_template.md")


def build_company_outreach_graph(company: str, role: str, personal_context: str, k: int = 6):
    tools = make_tools(k=k)
    planner = make_llm(temperature=0.0).bind_tools(tools)

    def agent_node(state: OutreachState):
        return {"messages": [*state["messages"], planner.invoke(state["messages"])]}

    def finalize_node(state: OutreachState):
        synth = make_llm(temperature=0.2)
        final_prompt = _FINAL_PROMPT_TEMPLATE.format(
            company=company,
            role=role,
            personal_context=personal_context or "(none provided)",
        )
        convo = [
            SystemMessage(content=OUTREACH_SYSTEM_PROMPT),
            *state["messages"],
            HumanMessage(content=final_prompt),
        ]
        msg = synth.invoke(convo)
        return {"messages": [*state["messages"], msg]}

    def tools_condition_local(state: OutreachState):
        msgs = state.get("messages", [])
        if not msgs:
            return END
        last = msgs[-1]
        if isinstance(last, AIMessage) and getattr(last, "tool_calls", None):
            return "tools"
        return END

    def tools_node(state: OutreachState):
        return run_tools_node(state, tools=tools, message_key="messages")

    graph = StateGraph(OutreachState)
    graph.add_node("agent", agent_node)
    graph.add_node("tools", tools_node)
    graph.add_node("finalize", finalize_node)

    graph.add_edge(START, "agent")
    graph.add_conditional_edges("agent", tools_condition_local, {"tools": "tools", END: "finalize"})
    graph.add_edge("tools", "agent")
    graph.add_edge("finalize", END)

    return graph.compile()


def agent():
    """LangGraph entrypoint for deployment.

    Note: this graph currently requires the runtime caller to provide company/role/context
    via the wrapper interface (service API). For LangSmith Deployment, consider
    migrating these into the state schema instead of closing over them.
    """

    # Default placeholder; callers should use `build_company_outreach_graph(...)`.
    return build_company_outreach_graph(company="(company)", role="(role)", personal_context="")
