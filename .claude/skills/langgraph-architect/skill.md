---
name: langgraph-architect
description: Principal-level LangGraph architect skill for designing, building, and reviewing production-grade AI agents. Use /langgraph to start a guided workflow for agent development. Covers architecture design, code quality review, state management patterns, error handling, and LangGraph best practices. Tailored to the agentic/ service patterns (BaseAgent, ReAct, MCP tools, AWS Bedrock).
---

# LangGraph Principal Architect Skill

A production-grade skill for designing, building, and reviewing LangGraph agents at principal engineer quality standards.

## Commands

| Command | Purpose |
|---------|---------|
| `/langgraph <description>` | Design and build a new agent |
| `/langgraph-review` | Review existing agent code for quality issues |
| `/langgraph-debug` | Analyze agent behavior and debug issues |

## Skill Philosophy

This skill embodies principal-level engineering principles:

1. **Architecture First**: Design before implementation
2. **Minimal Surface Area**: Only expose necessary tools and state
3. **Explicit Over Implicit**: Clear control flow, no magic
4. **Fail Fast, Recover Gracefully**: Robust error handling
5. **Observable by Default**: Built-in debugging and tracing

## When to Use This Skill

**Use for:**
- Designing new LangGraph agents
- Reviewing agent code quality
- Debugging agent behavior
- Refactoring existing agents
- Understanding LangGraph patterns

**Triggers:**
- "Build an agent that..."
- "Design a workflow for..."
- "Review my agent code"
- "Debug why my agent..."
- "Refactor this agent"

## Architecture Workflow

### Phase 1: Requirements Analysis
- What is the agent's mission?
- What inputs does it receive?
- What outputs must it produce?
- What external systems does it interact with?
- What are failure modes and recovery strategies?

### Phase 2: State Design
- Define minimal state schema
- Choose appropriate reducers for concurrent updates
- Plan checkpointing strategy
- Consider memory requirements (short-term vs long-term)

### Phase 3: Graph Topology
- Map nodes (processing units)
- Define edges (control flow)
- Identify conditional branching points
- Plan subgraph composition if needed

### Phase 4: Tool Selection
- Identify minimum required tools
- Apply principle of least privilege
- Document tool purposes
- Design tool error handling

### Phase 5: Implementation
- Write node functions
- Configure edges and conditions
- Add retry policies
- Implement streaming support

### Phase 6: Quality Review
- Verify state management
- Check error handling coverage
- Validate tool filtering
- Ensure observability

## Project Context

The `platform/agentic/` service architecture:

```
platform/agentic/
├── main.py                    # FastAPI /invocations endpoint
├── lois/                      # Agent implementations
│   ├── base_agent.py          # BaseAgent ReAct pattern
│   └── [agent_name].py        # Individual agents
├── clients/
│   └── mcp_client.py          # MCP Gateway tools
└── utils/
    └── tool_filter.py         # Tool allowlist filtering
```

## Integration Points

- **AWS Bedrock**: Claude models via ChatBedrock
- **MCP Gateway**: Tool access to Rails API
- **AgentCore**: Deployment, memory, checkpointing
- **Rails API**: Data access via REST endpoints
