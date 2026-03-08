# LangGraph Agent Templates

## Template 1: BaseAgent Extension (Project Standard)

Use this template for all agents in the `agentic/` service.

```python
"""
Agent Name - Brief Description

Detailed description of what this agent does and when it's used.
"""

import logging
from lois.base_agent import BaseAgent

logger = logging.getLogger(__name__)

# Tool Allowlist - Principle of Least Privilege
# Only include tools this agent absolutely needs
ALLOWED_TOOLS = [
    "getEmail",           # Fetch email content for processing
    "getUserDeals",       # List user's accessible deals
    "uploadDocumentToDeal", # Upload attachments to matched deal
]

SYSTEM_PROMPT = """You are [Agent Persona], an AI assistant for [purpose].

## Your Mission
[Clear description of what the agent should accomplish]

## Available Tools
- getEmail(email_id): Fetches email with attachments and signed URLs
- getUserDeals(user_id): Returns list of user's accessible deals
- uploadDocumentToDeal(deal_id, file_url, filename, user_id): Uploads document

## Process
1. [First step - what to analyze/fetch]
2. [Second step - decision making]
3. [Third step - action to take]
4. [Fourth step - response generation]

## Response Guidelines
- Be conversational and helpful
- Always explain your reasoning
- If uncertain, ask for clarification
- Sign off as "-[Agent Name]"

## Edge Cases
- If [scenario 1]: [how to handle]
- If [scenario 2]: [how to handle]
"""


class MyAgent(BaseAgent):
    """Agent for [purpose]."""

    @classmethod
    async def get_instance(cls, session_id: str):
        """Create agent instance with session-scoped tools.

        Args:
            session_id: Agentic session ID for MCP Gateway auth

        Returns:
            Configured agent instance
        """
        return await super().get_instance(
            allowed_tools=ALLOWED_TOOLS,
            system_prompt=SYSTEM_PROMPT,
            session_id=session_id
        )

    async def execute(self, params: dict, session_id: str) -> dict:
        """Execute the agent workflow.

        Args:
            params: Input from /invocations request
                - entity_id: Required identifier
                - optional_field: Optional parameter
            session_id: Session ID for auth and message sync

        Returns:
            dict with:
                - response_text: Human-readable response
                - success: Boolean indicating completion
                - [additional fields as needed]

        Raises:
            ValueError: If required params missing
        """
        # 1. Validate inputs
        entity_id = params.get("entity_id")
        if not entity_id:
            raise ValueError("entity_id is required")

        # 2. Build prompt with context
        prompt = f"""Process the request for entity {entity_id}.

[Additional context or instructions]"""

        # 3. Execute with message sync
        response_text = await self._stream_with_sync(
            prompt=prompt,
            session_id=session_id,
            actor_id="my_agent"
        )

        # 4. Return structured result
        return {
            "response_text": response_text,
            "success": True,
        }


async def get_agent(session_id: str) -> MyAgent:
    """Factory function for agent instantiation."""
    return await MyAgent.get_instance(session_id)
```

---

## Template 2: Standalone StateGraph Agent

Use when not extending BaseAgent (e.g., for simple workflows).

```python
"""
Simple Workflow Agent

Processes [input] and returns [output].
"""

import operator
from typing import Annotated, Literal
from typing_extensions import TypedDict

from langchain_aws import ChatBedrock
from langchain_core.messages import AnyMessage, SystemMessage
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver


class WorkflowState(TypedDict):
    """State for the workflow."""
    messages: Annotated[list[AnyMessage], operator.add]
    input_data: dict
    result: str | None
    error: str | None


def process_input(state: WorkflowState) -> dict:
    """Validate and prepare input."""
    input_data = state["input_data"]

    if not input_data.get("required_field"):
        return {"error": "required_field is missing"}

    return {"error": None}


def call_model(state: WorkflowState) -> dict:
    """Call LLM for processing."""
    if state.get("error"):
        return {}  # Skip if error

    llm = ChatBedrock(
        model_id="us.anthropic.claude-sonnet-4-5-20250929-v1:0",
        region_name="us-west-2"
    )

    messages = [
        SystemMessage(content="You are a helpful assistant."),
        *state["messages"]
    ]

    response = llm.invoke(messages)
    return {"messages": [response], "result": response.content}


def should_continue(state: WorkflowState) -> Literal["process", END]:
    """Route based on error state."""
    if state.get("error"):
        return END
    return "process"


def build_graph() -> StateGraph:
    """Construct the workflow graph."""
    graph = StateGraph(WorkflowState)

    # Add nodes
    graph.add_node("validate", process_input)
    graph.add_node("process", call_model)

    # Add edges
    graph.add_edge(START, "validate")
    graph.add_conditional_edges(
        "validate",
        should_continue,
        {"process": "process", END: END}
    )
    graph.add_edge("process", END)

    return graph


# Compile with checkpointing
memory = MemorySaver()
workflow = build_graph().compile(checkpointer=memory)


async def execute(input_data: dict, thread_id: str) -> dict:
    """Execute the workflow."""
    config = {"configurable": {"thread_id": thread_id}}

    result = await workflow.ainvoke(
        {
            "messages": [],
            "input_data": input_data,
            "result": None,
            "error": None
        },
        config
    )

    return {
        "result": result.get("result"),
        "error": result.get("error"),
        "success": result.get("error") is None
    }
```

---

## Template 3: Multi-Agent Supervisor

Use for complex workflows requiring multiple specialized agents.

```python
"""
Supervisor Agent

Orchestrates multiple specialized agents for complex tasks.
"""

import operator
from typing import Annotated, Literal
from typing_extensions import TypedDict

from langchain_aws import ChatBedrock
from langchain_core.messages import AnyMessage, SystemMessage
from langgraph.graph import StateGraph, START, END


class SupervisorState(TypedDict):
    """State for supervisor orchestration."""
    messages: Annotated[list[AnyMessage], operator.add]
    task: str
    next_agent: str | None
    agent_results: Annotated[list[dict], operator.add]
    final_result: str | None


SUPERVISOR_PROMPT = """You are a supervisor coordinating specialized agents.

Available agents:
- researcher: Gathers information and context
- analyzer: Processes data and finds patterns
- writer: Generates final output

Based on the current task and results so far, decide:
1. Which agent should work next
2. What they should do
3. Or if the task is complete

Respond with JSON: {"next_agent": "agent_name" | "done", "instruction": "..."}
"""


def supervisor(state: SupervisorState) -> dict:
    """Decide which agent to invoke next."""
    llm = ChatBedrock(
        model_id="us.anthropic.claude-sonnet-4-5-20250929-v1:0",
        region_name="us-west-2"
    )

    context = f"""
Task: {state["task"]}
Agent results so far: {state["agent_results"]}
"""

    messages = [
        SystemMessage(content=SUPERVISOR_PROMPT),
        ("user", context)
    ]

    response = llm.invoke(messages)
    # Parse response to get next_agent
    # (simplified - in production, use structured output)

    return {
        "messages": [response],
        "next_agent": "researcher"  # Parsed from response
    }


def researcher(state: SupervisorState) -> dict:
    """Research agent - gathers information."""
    # Implementation
    return {"agent_results": [{"agent": "researcher", "result": "..."}]}


def analyzer(state: SupervisorState) -> dict:
    """Analyzer agent - processes data."""
    # Implementation
    return {"agent_results": [{"agent": "analyzer", "result": "..."}]}


def writer(state: SupervisorState) -> dict:
    """Writer agent - generates output."""
    # Implementation
    return {"final_result": "...", "agent_results": [{"agent": "writer", "result": "..."}]}


def route_to_agent(state: SupervisorState) -> Literal["researcher", "analyzer", "writer", END]:
    """Route to next agent based on supervisor decision."""
    next_agent = state.get("next_agent")
    if next_agent == "done" or state.get("final_result"):
        return END
    return next_agent or END


def build_supervisor_graph() -> StateGraph:
    """Build the supervisor graph."""
    graph = StateGraph(SupervisorState)

    # Add nodes
    graph.add_node("supervisor", supervisor)
    graph.add_node("researcher", researcher)
    graph.add_node("analyzer", analyzer)
    graph.add_node("writer", writer)

    # Edges
    graph.add_edge(START, "supervisor")
    graph.add_conditional_edges("supervisor", route_to_agent)

    # All agents return to supervisor
    graph.add_edge("researcher", "supervisor")
    graph.add_edge("analyzer", "supervisor")
    graph.add_edge("writer", "supervisor")

    return graph
```

---

## main.py Integration Template

```python
# In main.py

from lois import get_my_agent

# Add to invocations() function:
elif agent_type == "my_agent":
    return await _invoke_my_agent(params, session_id)


async def _invoke_my_agent(params: dict, session_id: str) -> InvocationResponse:
    """Invoke the my_agent workflow."""
    try:
        agent = await get_my_agent(session_id)
        result = await agent.execute(params, session_id=session_id)

        return InvocationResponse(
            success=True,
            agent="my_agent",
            result=result,
            error=None
        )
    except ValueError as e:
        return InvocationResponse(
            success=False,
            agent="my_agent",
            result=None,
            error=str(e)
        )
    except Exception as e:
        logger.exception(f"my_agent failed: {e}")
        return InvocationResponse(
            success=False,
            agent="my_agent",
            result=None,
            error=f"Internal error: {str(e)}"
        )
```
