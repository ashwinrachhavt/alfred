# Solution B: Local MCP Server

> **Prerequisite:** Apply [local-dev-shared.md](local-dev-shared.md) first.

## Architecture

```
Rails :3000 ── HTTP POST ──> FastAPI :8080/invocations
                                  |
                          BaseAgent (ChatAnthropic)
                                  |
                          MCPGatewayClient (SAME as production)
                          connects to local MCP server :9090
                                  |
                          local_mcp_server.py receives MCP call_tool
                          dispatches to Rails :3000 via httpx
                                  |
                          Rails API (X-API-Key + session_id)
```

## Summary

| Aspect | Detail |
|---|---|
| **New files** | 1 (`agentic/local_mcp_server.py`) |
| **Modified files** | 2 (`mcp_client.py`, `base_agent.py`) |
| **Processes to run** | 3 (Rails + agents + MCP server) |
| **Tool discovery** | MCP protocol (same as production) |
| **Memory** | `SqliteSaver` (persistent across restarts) |
| **Production parity** | High — `tool_factory.py`, `schema_converter.py`, `tool_filter.py` ALL exercised |

---

## File 1: `agentic/local_mcp_server.py` (NEW)

```python
"""
Local MCP server for development.

Reads swagger.json and registers each operationId as an MCP tool.
When an agent calls a tool via MCP protocol, this server dispatches
the call to the Rails API via httpx.

This preserves the full MCP protocol path that the agent code uses
in production, including ClientSession, streamablehttp_client,
session.list_tools(), and session.call_tool().

Usage:
    python local_mcp_server.py
    # Starts MCP server on http://localhost:9090/mcp
"""

import json
import os
import sys
from pathlib import Path
from typing import Any

import httpx
from mcp.server.fastmcp import FastMCP

# -- Configuration --

RAILS_API_BASE = os.environ.get("RAILS_API_BASE", "http://localhost:3000")
BEDROCK_API_KEY = os.environ.get("BEDROCK_API_KEY", "local-dev-key")
MCP_PORT = int(os.environ.get("LOCAL_MCP_PORT", "9090"))

# Locate swagger.json
SWAGGER_PATH = os.environ.get("SWAGGER_PATH", "")
if not SWAGGER_PATH:
    candidates = [
        Path(__file__).parent.parent / "app" / "swagger" / "v1" / "swagger.json",
        Path(__file__).parent / "swagger.json",
    ]
    for candidate in candidates:
        if candidate.exists():
            SWAGGER_PATH = str(candidate)
            break

if not SWAGGER_PATH:
    print("ERROR: swagger.json not found. Set SWAGGER_PATH env var.", file=sys.stderr)
    sys.exit(1)

# -- Load spec --

with open(SWAGGER_PATH) as f:
    SPEC = json.load(f)

print(f"Loaded swagger spec from {SWAGGER_PATH}")

# -- Create MCP server --

mcp = FastMCP(
    "local-rails-gateway",
    instructions="Local development MCP gateway that proxies to Rails API",
)


def _build_rails_caller(method: str, path_template: str, params: list[dict]):
    """Build an async function that calls a specific Rails API endpoint."""
    path_param_names = {p["name"] for p in params if p.get("in") == "path"}
    query_param_names = {p["name"] for p in params if p.get("in") == "query"}

    async def call_rails(**kwargs: Any) -> Any:
        session_id = kwargs.pop("session_id", "")

        # Substitute path parameters
        path = path_template
        for name in list(path_param_names):
            if name in kwargs:
                path = path.replace(f"{{{name}}}", str(kwargs.pop(name)))

        # Build query params
        query_params = {"session_id": session_id}
        for k in list(kwargs.keys()):
            if k in query_param_names:
                query_params[k] = kwargs.pop(k)

        # Remaining kwargs become body
        body = kwargs if kwargs else None

        url = f"{RAILS_API_BASE}{path}"
        headers = {
            "Content-Type": "application/json",
            "X-API-Key": BEDROCK_API_KEY,
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            if method in ("post", "put", "patch"):
                response = await getattr(client, method)(
                    url, params=query_params, json=body, headers=headers
                )
            else:
                response = await getattr(client, method)(
                    url, params=query_params, headers=headers
                )

        print(f"  [{method.upper()}] {path} -> {response.status_code}")

        if response.status_code >= 400:
            return {"error": f"HTTP {response.status_code}", "detail": response.text}

        try:
            return response.json()
        except Exception:
            return {"raw": response.text}

    return call_rails


def _build_param_descriptions(params: list[dict], request_body: dict | None) -> str:
    """Build parameter documentation string for tool description."""
    lines = []
    for param in params:
        name = param["name"]
        req = "required" if param.get("required") else "optional"
        desc = param.get("description", "")
        ptype = param.get("schema", {}).get("type", "string")
        lines.append(f"  - {name} ({ptype}, {req}): {desc}")

    if request_body:
        body_schema = (
            request_body.get("content", {})
            .get("application/json", {})
            .get("schema", {})
        )
        for prop_name, prop_info in body_schema.get("properties", {}).items():
            ptype = prop_info.get("type", "string")
            desc = prop_info.get("description", "")
            lines.append(f"  - {prop_name} ({ptype}, body): {desc}")

    return "\n".join(lines)


# -- Register all swagger operations as MCP tools --

_tool_count = 0

for _path, _path_item in SPEC.get("paths", {}).items():
    _path_level_params = _path_item.get("parameters", [])

    for _method in ("get", "post", "put", "patch", "delete"):
        if _method not in _path_item:
            continue

        _operation = _path_item[_method]
        _operation_id = _operation.get("operationId")
        if not _operation_id:
            continue

        _description = _operation.get("description", _operation.get("summary", ""))
        _all_params = _path_level_params + _operation.get("parameters", [])
        _request_body = _operation.get("requestBody")

        _param_docs = _build_param_descriptions(_all_params, _request_body)
        if _param_docs:
            _full_description = f"{_description}\n\nParameters:\n{_param_docs}"
        else:
            _full_description = _description

        _caller = _build_rails_caller(_method, _path, _all_params)
        mcp.tool(name=_operation_id, description=_full_description)(_caller)
        _tool_count += 1

print(f"Registered {_tool_count} MCP tools from swagger.json")

# -- Run server --

if __name__ == "__main__":
    print(f"Starting local MCP server on http://localhost:{MCP_PORT}/mcp")
    mcp.run(transport="streamable-http", host="0.0.0.0", port=MCP_PORT)
```

---

## File 2: `agentic/clients/mcp_client.py`

**Change:** Skip Cognito auth when `LOCAL_MCP_URL` is set.

### Replace `__init__` (lines 23-57):

```python
def __init__(
    self,
    session_id: str,
    gateway_url: str | None = None,
    client_id: str | None = None,
    client_secret: str | None = None,
    token_url: str | None = None,
):
    """
    Initialize the MCP gateway client.

    In local mode (LOCAL_MCP_URL set), connects to local MCP server
    without authentication. In production, uses Cognito OAuth2.
    """
    self.session_id = session_id
    self.local_mode = bool(os.environ.get("LOCAL_MCP_URL"))

    if self.local_mode:
        self.gateway_url = os.environ["LOCAL_MCP_URL"]
        self.authenticator = None
    else:
        self.client_id = client_id or os.environ.get("COGNITO_CLIENT_ID", "")
        self.client_secret = client_secret or os.environ.get("COGNITO_CLIENT_SECRET", "")
        self.token_url = token_url or os.environ.get("COGNITO_TOKEN_URL", "")
        self.gateway_url = gateway_url or os.environ.get("GATEWAY_URL", "")
        self.authenticator = CognitoAuthenticator(
            client_id=self.client_id,
            client_secret=self.client_secret or "",
            token_url=self.token_url,
        )

    self.tool_factory = MCPToolFactory()
```

### Replace `get_tools` (lines 59-114):

```python
async def get_tools(self) -> list[Tool]:
    """Get tools from the MCP gateway (local or remote)."""
    if self.local_mode:
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
    else:
        access_token = self.authenticator.get_token()
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "Authorization": f"Bearer {access_token}",
        }

    async with streamablehttp_client(self.gateway_url, headers=headers) as (
        read, write, _,
    ):
        async with ClientSession(read, write) as session:
            await session.initialize()
            list_tools_response = await session.list_tools()
            tools_info = list_tools_response.tools

            tools = []
            for tool_info in tools_info:
                tool_name = tool_info.name
                description = (
                    tool_info.description
                    if hasattr(tool_info, "description")
                    else ""
                )

                input_schema = None
                output_schema = None

                if hasattr(tool_info, "inputSchema") and tool_info.inputSchema:
                    input_schema = tool_info.inputSchema
                if hasattr(tool_info, "outputSchema") and tool_info.outputSchema:
                    output_schema = tool_info.outputSchema

                invoke_specific_tool = self._create_invoke_func(tool_name)
                tool = self.tool_factory.create_tool(
                    tool_name=tool_name,
                    description=description,
                    invoke_func=invoke_specific_tool,
                    input_schema=input_schema,
                    output_schema=output_schema,
                )
                tools.append(tool)

            return tools
```

### Replace `_create_invoke_func` (lines 116-168):

```python
def _create_invoke_func(self, tool_name: str) -> Callable:
    """Create an invoke function for a specific tool."""

    async def specific_invoke_tool(parameters: dict[str, Any]) -> Any:
        logger.info(f"Tool call: {tool_name}")

        if self.local_mode:
            headers = {
                "Accept": "application/json",
                "Content-Type": "application/json",
            }
        else:
            access_token = self.authenticator.get_token()
            headers = {
                "Accept": "application/json",
                "Content-Type": "application/json",
                "Authorization": f"Bearer {access_token}",
            }

        parameters_with_session = {**parameters, "session_id": self.session_id}
        logger.info(f"Injecting session_id into parameters: {self.session_id}")

        async with streamablehttp_client(self.gateway_url, headers=headers) as (
            read, write, _,
        ):
            async with ClientSession(read, write) as new_session:
                await new_session.initialize()
                result = await new_session.call_tool(
                    tool_name, parameters_with_session
                )

                is_error = getattr(result, "isError", False)
                if is_error:
                    content_text = ""
                    if hasattr(result, "content") and result.content:
                        content_text = (
                            result.content[0].text if result.content else ""
                        )
                    logger.error(f"Tool error ({tool_name}): {content_text[:500]}")
                else:
                    logger.info(f"Tool response ({tool_name}): success")

                return result

    return specific_invoke_tool
```

---

## File 3: `agentic/lois/agents/base_agent.py`

**Change:** Tools section UNCHANGED (uses `get_gateway_tools` which calls `MCPGatewayClient`). Only memory section changes to use `SqliteSaver`.

Full copy-paste ready method:

```python
@classmethod
async def get_instance(
    cls, allowed_tools: list[str], system_prompt: str, session_id: str
) -> Self:
    """Create a fresh agent instance with session ID.

    In local mode: ChatAnthropic/ChatOpenAI + local MCP server + SqliteSaver.
    In production: ChatBedrock + MCP Gateway + AgentCoreMemorySaver.
    """
    # --- LLM ---
    if os.environ.get("ANTHROPIC_API_KEY"):
        from langchain_anthropic import ChatAnthropic

        llm = ChatAnthropic(
            model="claude-sonnet-4-5-20250514",
            max_tokens=4096,
            temperature=0,
        )
    elif os.environ.get("OPENAI_API_KEY"):
        from langchain_openai import ChatOpenAI

        llm = ChatOpenAI(
            model=os.environ.get("OPENAI_MODEL", "gpt-4o"),
            max_tokens=4096,
            temperature=0,
        )
    else:
        llm = ChatBedrock(
            model_id="us.anthropic.claude-sonnet-4-5-20250929-v1:0",
            region_name="us-west-2",
            model_kwargs={"max_tokens": 4096, "temperature": 0},
        )

    # --- Tools (uses MCPGatewayClient — unchanged from production) ---
    all_tools = await get_gateway_tools(session_id=session_id)
    tools = filter_tools(all_tools, allowed_tools)
    logger.info("%s filtered to %d allowed tools", cls.__name__, len(tools))

    # --- Memory / Checkpointer ---
    memory_id = os.environ.get("AGENTCORE_MEMORY_ID", "")
    if memory_id:
        checkpointer = AgentCoreMemorySaver(memory_id, region_name="us-west-2")
    else:
        from langgraph.checkpoint.sqlite import SqliteSaver

        db_path = os.environ.get("CHECKPOINT_DB", "checkpoints.db")
        checkpointer = SqliteSaver.from_conn_string(db_path)

    return cls(llm, tools, checkpointer, system=system_prompt)
```

---

## File 4: `agentic/requirements.txt`

**Change:** Add `SqliteSaver` dependency (in addition to shared `langchain-anthropic`).

```
langgraph-checkpoint-sqlite>=2.0.0
```

---

## Environment Variables (Solution B specific)

In addition to [shared env vars](local-dev-shared.md#environment-variables-shared):

```bash
# Agentic .env
LOCAL_MCP_URL=http://localhost:9090/mcp          # triggers local MCP mode
GATEWAY_URL=                                      # leave empty
CHECKPOINT_DB=checkpoints.db                      # optional, defaults to checkpoints.db
SWAGGER_PATH=../app/swagger/v1/swagger.json       # for MCP server, optional
```

---

## How to Run

**Terminal 1 — Rails:**

```bash
cd app
LOCAL_AGENTIC_URL=http://localhost:8080 BEDROCK_API_KEY=local-dev-key bin/dev
```

**Terminal 2 — Local MCP server:**

```bash
cd agentic
source venv/bin/activate
export RAILS_API_BASE=http://localhost:3000 BEDROCK_API_KEY=local-dev-key
python local_mcp_server.py
```

**Terminal 3 — Agents:**

```bash
cd agentic
source venv/bin/activate
export LOCAL_MCP_URL=http://localhost:9090/mcp \
       RAILS_API_BASE=http://localhost:3000 \
       BEDROCK_API_KEY=local-dev-key \
       ANTHROPIC_API_KEY=sk-ant-...
python main.py
```

**Or with overmind/foreman (`Procfile.local`):**

```
web:    cd app && LOCAL_AGENTIC_URL=http://localhost:8080 BEDROCK_API_KEY=local-dev-key bin/dev
mcp:    cd agentic && RAILS_API_BASE=http://localhost:3000 BEDROCK_API_KEY=local-dev-key python local_mcp_server.py
agents: cd agentic && LOCAL_MCP_URL=http://localhost:9090/mcp RAILS_API_BASE=http://localhost:3000 BEDROCK_API_KEY=local-dev-key ANTHROPIC_API_KEY=sk-ant-... python main.py
```

---

## Tradeoffs

| Pro | Con |
|---|---|
| Highest production parity — full MCP protocol exercised | Extra process to manage (MCP server) |
| `tool_factory.py`, `schema_converter.py`, `tool_filter.py` untouched | Building `local_mcp_server.py` is ~150 lines |
| `SqliteSaver` persists across restarts | Two levels of HTTP (agent -> MCP -> Rails) |
| Catches MCP-layer bugs locally | More complex debugging (3 processes) |
