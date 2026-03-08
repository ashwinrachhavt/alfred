# LangGraph Architecture Patterns

## Core Concepts

### StateGraph
The fundamental building block of LangGraph. Defines a directed graph where:
- **Nodes**: Functions that process and update state
- **Edges**: Connections defining control flow
- **State**: TypedDict holding workflow data

```python
from langgraph.graph import StateGraph, START, END
from typing_extensions import TypedDict

class State(TypedDict):
    messages: list
    context: dict

graph = StateGraph(State)
graph.add_node("process", process_fn)
graph.add_edge(START, "process")
graph.add_edge("process", END)
app = graph.compile()
```

### State Reducers
Use `Annotated` with reducer functions for concurrent state updates:

```python
import operator
from typing import Annotated

class State(TypedDict):
    # Override behavior (default)
    current_value: str

    # Append behavior (use for messages, logs)
    messages: Annotated[list, operator.add]

    # Custom reducer
    counter: Annotated[int, lambda a, b: a + b]
```

**When to use reducers:**
- Multiple nodes write to same key
- Parallel execution paths
- Message accumulation (always use `operator.add`)

### Conditional Edges
Branch execution based on state:

```python
from typing import Literal

def route_decision(state: State) -> Literal["path_a", "path_b", END]:
    if state["needs_tool"]:
        return "path_a"
    elif state["needs_review"]:
        return "path_b"
    return END

graph.add_conditional_edges(
    "decision_node",
    route_decision,
    {
        "path_a": "tool_node",
        "path_b": "review_node",
        END: END
    }
)
```

---

## Agent Patterns

### ReAct Pattern (Reasoning + Acting)
The standard pattern for tool-using agents:

```python
def should_continue(state: State) -> Literal["tools", END]:
    last_message = state["messages"][-1]
    if hasattr(last_message, "tool_calls") and last_message.tool_calls:
        return "tools"
    return END

graph.add_node("llm", call_model)
graph.add_node("tools", tool_node)
graph.add_edge(START, "llm")
graph.add_conditional_edges("llm", should_continue, ["tools", END])
graph.add_edge("tools", "llm")
```

**Key characteristics:**
- LLM decides what tool to call
- Tool results feed back to LLM
- Loops until LLM produces final answer

### Router Pattern
For multi-path workflows based on classification:

```python
def classify_and_route(state: State) -> Literal["type_a", "type_b", "type_c"]:
    classification = state["classification"]
    return classification["type"]

graph.add_node("classifier", classify_input)
graph.add_node("type_a_handler", handle_type_a)
graph.add_node("type_b_handler", handle_type_b)
graph.add_node("type_c_handler", handle_type_c)

graph.add_edge(START, "classifier")
graph.add_conditional_edges("classifier", classify_and_route)
graph.add_edge("type_a_handler", END)
graph.add_edge("type_b_handler", END)
graph.add_edge("type_c_handler", END)
```

### Supervisor Pattern
For multi-agent orchestration:

```python
class SupervisorState(TypedDict):
    messages: Annotated[list, operator.add]
    next_agent: str
    completed_agents: list

def supervisor(state: SupervisorState) -> dict:
    # LLM decides which agent to invoke next
    response = llm.invoke(state["messages"])
    return {"next_agent": response.content}

def route_to_agent(state: SupervisorState) -> str:
    return state["next_agent"]

graph.add_node("supervisor", supervisor)
graph.add_node("agent_a", agent_a_fn)
graph.add_node("agent_b", agent_b_fn)
graph.add_conditional_edges("supervisor", route_to_agent)
```

---

## Memory & Persistence

### Checkpointing
Enable state persistence across invocations:

```python
from langgraph.checkpoint.memory import MemorySaver

checkpointer = MemorySaver()
app = graph.compile(checkpointer=checkpointer)

# Invoke with thread_id for persistence
config = {"configurable": {"thread_id": "user-123"}}
result = app.invoke({"messages": [...]}, config)
```

### Long-term Memory (Store)
For cross-session memory:

```python
from langgraph.store.memory import InMemoryStore

store = InMemoryStore()
app = graph.compile(checkpointer=checkpointer, store=store)

# In node function:
async def call_model(state, config, *, store):
    user_id = config["configurable"]["user_id"]
    namespace = ("memories", user_id)
    memories = await store.asearch(namespace)
    # Use memories in context
```

### AgentCore Memory (Production)
For AWS deployment:

```python
from langgraph_checkpoint_aws import AgentCoreMemorySaver

memory_id = os.environ["AGENTCORE_MEMORY_ID"]
checkpointer = AgentCoreMemorySaver(memory_id, region_name="us-west-2")
```

---

## Error Handling

### Retry Policies
Add automatic retries for transient failures:

```python
from langgraph.types import RetryPolicy

graph.add_node(
    "api_call",
    call_external_api,
    retry_policy=RetryPolicy(
        max_attempts=3,
        initial_interval=1.0,
        backoff_multiplier=2.0
    )
)
```

### Graceful Degradation
Handle tool failures without crashing:

```python
def safe_tool_call(state: State) -> dict:
    try:
        result = tool.invoke(state["input"])
        return {"result": result, "error": None}
    except Exception as e:
        return {"result": None, "error": str(e)}
```

### Recursion Limits
Prevent infinite loops:

```python
config = {"recursion_limit": 50}
result = app.invoke(input, config)
```

---

## Streaming

### Stream Mode Options
```python
# Stream state updates
async for update in graph.astream(input, config, stream_mode="updates"):
    print(update)

# Stream final values only
async for chunk in graph.astream(input, config, stream_mode="values"):
    chunk["messages"][-1].pretty_print()

# Stream events (most detailed)
async for event in graph.astream_events(input, config, version="v2"):
    if event["event"] == "on_chat_model_end":
        # Handle LLM completion
        pass
```

---

## Subgraphs

### Composing Graphs
```python
# Define subgraph
subgraph_builder = StateGraph(SubState)
subgraph_builder.add_node("sub_process", sub_process_fn)
subgraph = subgraph_builder.compile()

# Use in parent
parent_builder = StateGraph(ParentState)
parent_builder.add_node("sub_workflow", subgraph)
parent_builder.add_edge(START, "sub_workflow")
```

### Subgraph with Independent Memory
```python
# Subgraph maintains its own message history
subgraph = subgraph_builder.compile(checkpointer=True)
```

---

## Anti-Patterns to Avoid

### 1. God State
**Bad:** State with 20+ keys
**Good:** Minimal state with focused keys

### 2. Deep Nesting
**Bad:** Conditional edges with 10+ branches
**Good:** Use router pattern with clear classification

### 3. Silent Failures
**Bad:** `except: pass`
**Good:** Log errors, update state with error info

### 4. Unbounded Loops
**Bad:** ReAct loop without termination condition
**Good:** Always have recursion_limit and explicit END conditions

### 5. Tool Overload
**Bad:** Agent with 50 available tools
**Good:** Filter to minimum required tools per agent
