# Solution A: Direct HTTP + Swagger Tools

> **Prerequisite:** Apply [local-dev-shared.md](local-dev-shared.md) first.

## Architecture

```
Rails :3000 ── HTTP POST ──> FastAPI :8080/invocations
                                  |
                          BaseAgent (ChatAnthropic)
                                  |
                          swagger_tool_client reads swagger.json
                          builds StructuredTool per operationId
                                  |
                          tool.invoke() ── httpx ──> Rails :3000/api/v1/...
```

## Summary

| Aspect | Detail |
|---|---|
| **New files** | 1 (`agentic/clients/swagger_tool_client.py`) |
| **Modified files** | 1 (`agentic/lois/agents/base_agent.py` — tools section) |
| **Processes to run** | 2 (Rails + agents) |
| **Tool discovery** | Dynamic — parses `swagger.json` at startup |
| **Memory** | `MemorySaver` (in-memory, lost on restart) |
| **Production parity** | Medium — exercises `MCPToolFactory` + `SchemaConverter` but not MCP protocol |

---

## File 1: `agentic/clients/swagger_tool_client.py` (NEW)

```python
"""
Swagger-based tool client for local development.

Reads the OpenAPI spec (swagger.json) and creates LangChain StructuredTools
that call the Rails API directly via httpx, bypassing MCP Gateway entirely.

Uses the existing MCPToolFactory and SchemaConverter for consistent tool shapes,
so the agent sees identical tool signatures to production.
"""

import json
import os
import re
from pathlib import Path
from typing import Any

import httpx

from clients.schema_converter import SchemaConverter
from clients.tool_factory import MCPToolFactory
from core.logger import get_logger

logger = get_logger(__name__)


class SwaggerToolClient:
    """Creates LangChain tools from swagger.json, calling Rails API via httpx."""

    def __init__(self, session_id: str):
        self.session_id = session_id
        self.rails_url = os.environ.get("RAILS_API_BASE", "http://localhost:3000")
        self.api_key = os.environ.get("BEDROCK_API_KEY", "local-dev-key")
        self.tool_factory = MCPToolFactory()

        # Locate swagger.json — check env, then try relative to project root
        swagger_path = os.environ.get("SWAGGER_PATH", "")
        if not swagger_path:
            candidates = [
                Path(__file__).parent.parent.parent / "app" / "swagger" / "v1" / "swagger.json",
                Path(__file__).parent.parent / "swagger.json",
            ]
            for candidate in candidates:
                if candidate.exists():
                    swagger_path = str(candidate)
                    break

        if not swagger_path:
            raise FileNotFoundError(
                "swagger.json not found. Set SWAGGER_PATH or ensure "
                "app/swagger/v1/swagger.json exists."
            )

        with open(swagger_path) as f:
            self.spec = json.load(f)

        logger.info("Loaded swagger spec from %s", swagger_path)

    def get_tools(self) -> list:
        """Build LangChain StructuredTools from every operation in the spec."""
        tools = []

        for path, path_item in self.spec.get("paths", {}).items():
            path_level_params = path_item.get("parameters", [])

            for method in ("get", "post", "put", "patch", "delete"):
                if method not in path_item:
                    continue

                operation = path_item[method]
                operation_id = operation.get("operationId")
                if not operation_id:
                    logger.warning("Skipping %s %s — no operationId", method.upper(), path)
                    continue

                description = operation.get("description", operation.get("summary", ""))
                all_params = path_level_params + operation.get("parameters", [])
                input_schema = self._build_input_schema(all_params, operation.get("requestBody"))
                invoke_func = self._create_invoke_func(method, path, all_params, operation.get("requestBody"))

                tool = self.tool_factory.create_tool(
                    tool_name=operation_id,
                    description=description,
                    invoke_func=invoke_func,
                    input_schema=input_schema,
                )
                tools.append(tool)
                logger.debug("Registered tool: %s (%s %s)", operation_id, method.upper(), path)

        logger.info("Built %d tools from swagger.json", len(tools))
        return tools

    def _build_input_schema(
        self, params: list[dict], request_body: dict | None
    ) -> dict[str, Any]:
        """Convert OpenAPI parameters + requestBody into a JSON Schema.

        Excludes session_id since it's injected automatically.
        """
        properties = {}
        required = []

        for param in params:
            name = param["name"]
            if name == "session_id":
                continue

            schema = param.get("schema", {"type": "string"})
            properties[name] = {
                "type": schema.get("type", "string"),
                "description": param.get("description", f"The {name} parameter"),
            }
            if param.get("required"):
                required.append(name)

        if request_body:
            body_schema = (
                request_body.get("content", {})
                .get("application/json", {})
                .get("schema", {})
            )
            for prop_name, prop_schema in body_schema.get("properties", {}).items():
                if prop_name == "session_id":
                    continue
                properties[prop_name] = prop_schema
                if prop_name in body_schema.get("required", []):
                    required.append(prop_name)

        return {"type": "object", "properties": properties, "required": required}

    def _create_invoke_func(
        self, method: str, path_template: str, params: list[dict], request_body: dict | None
    ):
        """Create an async function that calls the Rails API directly."""
        path_param_names = {p["name"] for p in params if p.get("in") == "path"}
        query_param_names = {p["name"] for p in params if p.get("in") == "query"}

        async def invoke(parameters: dict[str, Any]) -> Any:
            # Substitute path parameters
            path = path_template
            for name in path_param_names:
                if name in parameters:
                    path = path.replace(f"{{{name}}}", str(parameters[name]))

            # Build query params — always include session_id
            query_params = {"session_id": self.session_id}
            for k, v in parameters.items():
                if k in query_param_names and k != "session_id":
                    query_params[k] = v

            # Everything not a path/query param goes in the body
            body_params = {
                k: v
                for k, v in parameters.items()
                if k not in path_param_names and k not in query_param_names
            }

            url = f"{self.rails_url}{path}"
            headers = {
                "Content-Type": "application/json",
                "X-API-Key": self.api_key,
            }

            async with httpx.AsyncClient(timeout=30.0) as client:
                if method in ("post", "put", "patch"):
                    response = await getattr(client, method)(
                        url, params=query_params, json=body_params, headers=headers
                    )
                else:
                    response = await getattr(client, method)(
                        url, params=query_params, headers=headers
                    )

            logger.info("API %s %s -> %s", method.upper(), path, response.status_code)

            if response.status_code >= 400:
                return {"error": f"HTTP {response.status_code}", "detail": response.text}

            try:
                return response.json()
            except Exception:
                return {"raw": response.text}

        return invoke


async def get_swagger_tools(session_id: str) -> list:
    """Helper matching the signature of get_gateway_tools()."""
    client = SwaggerToolClient(session_id=session_id)
    return client.get_tools()
```

---

## File 2: `agentic/lois/agents/base_agent.py`

**Change:** Replace the `--- Tools ---` section in `get_instance()`.

Full copy-paste ready method (includes shared LLM + memory from `local-dev-shared.md`):

```python
@classmethod
async def get_instance(
    cls, allowed_tools: list[str], system_prompt: str, session_id: str
) -> Self:
    """Create a fresh agent instance with session ID.

    Supports local mode (ANTHROPIC_API_KEY or OPENAI_API_KEY set,
    GATEWAY_URL empty) and production mode (AWS Bedrock + MCP Gateway).
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

    # --- Tools ---
    gateway_url = os.environ.get("GATEWAY_URL", "")
    if not gateway_url:
        from clients.swagger_tool_client import get_swagger_tools

        all_tools = await get_swagger_tools(session_id=session_id)
    else:
        all_tools = await get_gateway_tools(session_id=session_id)

    tools = filter_tools(all_tools, allowed_tools)
    logger.info("%s filtered to %d allowed tools", cls.__name__, len(tools))

    # --- Memory / Checkpointer ---
    memory_id = os.environ.get("AGENTCORE_MEMORY_ID", "")
    if memory_id:
        checkpointer = AgentCoreMemorySaver(memory_id, region_name="us-west-2")
    else:
        from langgraph.checkpoint.memory import MemorySaver

        checkpointer = MemorySaver()

    return cls(llm, tools, checkpointer, system=system_prompt)
```

---

## Environment Variables (Solution A specific)

In addition to [shared env vars](local-dev-shared.md#environment-variables-shared):

```bash
# Agentic .env
GATEWAY_URL=                                    # empty — triggers swagger mode
SWAGGER_PATH=../app/swagger/v1/swagger.json     # optional, auto-detected
```

---

## How to Run

**Terminal 1 — Rails:**

```bash
cd app
LOCAL_AGENTIC_URL=http://localhost:8080 BEDROCK_API_KEY=local-dev-key bin/dev
```

**Terminal 2 — Agents:**

```bash
cd agentic
source venv/bin/activate
export GATEWAY_URL="" \
       RAILS_API_BASE=http://localhost:3000 \
       BEDROCK_API_KEY=local-dev-key \
       ANTHROPIC_API_KEY=sk-ant-...
python main.py
```

**Or with overmind/foreman (`Procfile.local`):**

```
web:    cd app && LOCAL_AGENTIC_URL=http://localhost:8080 BEDROCK_API_KEY=local-dev-key bin/dev
agents: cd agentic && GATEWAY_URL="" RAILS_API_BASE=http://localhost:3000 BEDROCK_API_KEY=local-dev-key ANTHROPIC_API_KEY=sk-ant-... python main.py
```

---

## Tradeoffs

| Pro | Con |
|---|---|
| Fewest new files (1 Rails, 1 Python) | `swagger.json` can go stale if regeneration forgotten |
| Reuses existing `MCPToolFactory` + `SchemaConverter` | Doesn't exercise MCP protocol path at all |
| No extra processes to run | `MemorySaver` loses state on restart |
| Fastest to implement (~2 hours) | Tool names differ from production (no prefix) |
