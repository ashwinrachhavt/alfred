# LangGraph Debugging Guide

## Common Issues and Solutions

### Issue 1: Agent Loops Infinitely

**Symptoms:**
- Agent keeps calling tools without stopping
- Recursion limit reached error
- High token usage

**Root Causes:**
1. Missing END condition in conditional edges
2. Tool always returns result that triggers another call
3. System prompt doesn't instruct when to stop

**Solutions:**

```python
# 1. Ensure END is always reachable
def should_continue(state: State) -> Literal["tools", END]:
    last_message = state["messages"][-1]

    # Explicit termination conditions
    if not hasattr(last_message, "tool_calls"):
        return END
    if not last_message.tool_calls:
        return END

    return "tools"

# 2. Set recursion limit
config = {"recursion_limit": 25}
result = app.invoke(input, config)

# 3. Add iteration counter to state
class State(TypedDict):
    messages: Annotated[list, operator.add]
    iterations: int

def check_iterations(state: State) -> Literal["continue", END]:
    if state["iterations"] >= 10:
        return END
    return "continue"
```

---

### Issue 2: State Not Updating

**Symptoms:**
- Node returns data but state doesn't change
- Subsequent nodes see old values

**Root Causes:**
1. Node returns wrong key name
2. Missing reducer for list fields
3. Returning `None` instead of empty dict

**Solutions:**

```python
# 1. Return exact key names from State
class State(TypedDict):
    result: str  # Must return {"result": "..."}, not {"output": "..."}

# 2. Use reducer for concurrent updates
class State(TypedDict):
    messages: Annotated[list, operator.add]  # Not just `list`

# 3. Always return dict, even if empty
def node_fn(state: State) -> dict:
    if condition:
        return {"result": "value"}
    return {}  # Not None
```

---

### Issue 3: Tool Calls Failing

**Symptoms:**
- `KeyError: 'tool_name'`
- Tool not found errors
- Auth failures

**Root Causes:**
1. Tool not in ALLOWED_TOOLS
2. Tool name mismatch (case sensitive)
3. Session ID not propagated

**Solutions:**

```python
# 1. Verify tool name exactly matches MCP Gateway
ALLOWED_TOOLS = [
    "getUserDeals",  # Exact case matters!
]

# 2. Debug available tools
all_tools = await get_gateway_tools(session_id)
print([t.name for t in all_tools])  # See actual names

# 3. Ensure session_id flows through
agent = await MyAgent.get_instance(session_id)  # Pass here
result = await agent.execute(params, session_id=session_id)  # And here
```

---

### Issue 4: Empty Messages Error (Bedrock)

**Symptoms:**
- "Messages cannot be empty"
- "Content must be non-empty"

**Root Causes:**
1. Tool call messages have empty content
2. Filtered messages list becomes empty

**Solutions:**

```python
# BaseAgent already handles this with _filter_empty_messages
# But ensure you're not creating empty messages:

def node_fn(state: State) -> dict:
    # Bad: empty content
    return {"messages": [AIMessage(content="")]}

    # Good: meaningful content
    return {"messages": [AIMessage(content="Processing complete.")]}

# Or skip message entirely
def node_fn(state: State) -> dict:
    return {}  # Don't add message if nothing to say
```

---

### Issue 5: Checkpointing Not Working

**Symptoms:**
- State resets between invocations
- Thread isolation not working

**Root Causes:**
1. Checkpointer not passed to compile()
2. Missing thread_id in config
3. Wrong config structure

**Solutions:**

```python
# 1. Compile with checkpointer
from langgraph.checkpoint.memory import MemorySaver

checkpointer = MemorySaver()
app = graph.compile(checkpointer=checkpointer)

# 2. Always pass thread_id
config = {
    "configurable": {
        "thread_id": session_id,  # Required!
    }
}
result = app.invoke(input, config)

# 3. For AgentCore (production)
from langgraph_checkpoint_aws import AgentCoreMemorySaver

memory_id = os.environ["AGENTCORE_MEMORY_ID"]
checkpointer = AgentCoreMemorySaver(memory_id, region_name="us-west-2")
```

---

### Issue 6: Streaming Not Returning Events

**Symptoms:**
- astream() returns nothing
- Events missing expected data

**Root Causes:**
1. Wrong stream_mode
2. Not iterating async generator
3. Event filtering too aggressive

**Solutions:**

```python
# 1. Use correct stream_mode for your needs
# "updates" - state changes only
# "values" - full state at each step
# "events" - detailed event stream (via astream_events)

# 2. Properly iterate async generator
async for event in graph.astream_events(input, config, version="v2"):
    if event["event"] == "on_chat_model_end":
        output = event["data"]["output"]
        print(output.content)

# 3. Check event types
async for event in graph.astream_events(input, config, version="v2"):
    print(f"Event: {event['event']}, Name: {event.get('name')}")
```

---

## Debugging Techniques

### 1. Print State at Each Node

```python
def debug_node(state: State) -> dict:
    print(f"=== NODE: debug_node ===")
    print(f"Messages: {len(state['messages'])}")
    print(f"Last message: {state['messages'][-1] if state['messages'] else 'None'}")
    print(f"Full state: {state}")
    print("=" * 40)
    return {}

# Add between nodes for visibility
graph.add_node("debug", debug_node)
graph.add_edge("node_a", "debug")
graph.add_edge("debug", "node_b")
```

### 2. Visualize Graph Structure

```python
# Generate Mermaid diagram
print(graph.get_graph().draw_mermaid())

# Or save as PNG (requires graphviz)
from IPython.display import Image
Image(graph.get_graph().draw_mermaid_png())
```

### 3. Trace Tool Calls

```python
def traced_tool_node(state: State) -> dict:
    tool_calls = state["messages"][-1].tool_calls

    for tc in tool_calls:
        print(f"Tool: {tc['name']}")
        print(f"Args: {tc['args']}")

    # Execute tools
    results = []
    for tc in tool_calls:
        try:
            result = tools[tc["name"]].invoke(tc["args"])
            print(f"Result: {result[:200]}...")
            results.append(ToolMessage(
                content=str(result),
                tool_call_id=tc["id"],
                name=tc["name"]
            ))
        except Exception as e:
            print(f"Error: {e}")
            results.append(ToolMessage(
                content=f"Error: {e}",
                tool_call_id=tc["id"],
                name=tc["name"]
            ))

    return {"messages": results}
```

### 4. Log Configuration

```python
import logging

# Enable LangGraph debug logging
logging.getLogger("langgraph").setLevel(logging.DEBUG)

# Or more selective
logging.getLogger("langgraph.graph").setLevel(logging.DEBUG)
```

---

## Performance Debugging

### Identify Slow Nodes

```python
import time

def timed_node(fn):
    async def wrapper(state):
        start = time.time()
        result = await fn(state)
        duration = time.time() - start
        print(f"{fn.__name__} took {duration:.2f}s")
        return result
    return wrapper

@timed_node
async def slow_node(state: State) -> dict:
    # Your logic
    pass
```

### Token Usage Tracking

```python
def call_model(state: State) -> dict:
    response = llm.invoke(state["messages"])

    # Log token usage
    if hasattr(response, "usage_metadata"):
        usage = response.usage_metadata
        print(f"Input tokens: {usage.get('input_tokens')}")
        print(f"Output tokens: {usage.get('output_tokens')}")

    return {"messages": [response]}
```
