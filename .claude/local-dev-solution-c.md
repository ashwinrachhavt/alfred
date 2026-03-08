# Solution C: Rails-Native Hardcoded Tools

> **Prerequisite:** Apply [local-dev-shared.md](local-dev-shared.md) first.

## Architecture

```
Rails :3000 ── HTTP POST ──> FastAPI :8080/invocations
                                  |
                          BaseAgent (ChatAnthropic)
                                  |
                          local_rails_tools.get_local_tools()
                          returns @tool-decorated functions
                                  |
                          tool.invoke() ── httpx ──> Rails :3000/api/v1/...
                          (direct, no MCP, no swagger)
```

## Summary

| Aspect | Detail |
|---|---|
| **New files** | 1 (`agentic/clients/local_rails_tools.py`) |
| **Modified files** | 1 (`agentic/lois/agents/base_agent.py` — tools section) |
| **Processes to run** | 2 (Rails + agents) |
| **Tool discovery** | Static — 13 hardcoded `@tool` functions |
| **Memory** | `MemorySaver` (in-memory, lost on restart) |
| **Production parity** | Low — does not exercise MCP, `tool_factory`, or `schema_converter` |

---

## File 1: `agentic/clients/local_rails_tools.py` (NEW)

```python
"""
Hardcoded Rails API tools for local development.

Each tool is a simple Python function that calls a specific Rails API endpoint
via httpx. No MCP protocol, no swagger parsing, no dynamic schema conversion.

Tools are organized to match the operationId values from swagger.json so that
agent ALLOWED_TOOLS lists work unchanged.

Usage:
    tools = get_local_tools(session_id="uuid-123", allowed_tools=["getEmail", "listDeals"])
"""

import os
from typing import Any

import httpx
from langchain_core.tools import tool
from pydantic import BaseModel, Field

from core.logger import get_logger

logger = get_logger(__name__)


class _RailsAPI:
    """Shared HTTP client configuration for all tools."""

    def __init__(self, session_id: str):
        self.session_id = session_id
        self.base_url = os.environ.get("RAILS_API_BASE", "http://localhost:3000")
        self.api_key = os.environ.get("BEDROCK_API_KEY", "local-dev-key")
        self.headers = {
            "Content-Type": "application/json",
            "X-API-Key": self.api_key,
        }

    def get(self, path: str, params: dict | None = None) -> dict:
        """GET request to Rails API."""
        params = {**(params or {}), "session_id": self.session_id}
        url = f"{self.base_url}{path}"
        logger.info("GET %s", url)
        with httpx.Client(timeout=30.0) as client:
            r = client.get(url, params=params, headers=self.headers)
        if r.status_code >= 400:
            return {"error": f"HTTP {r.status_code}", "detail": r.text}
        return r.json()

    def post(self, path: str, body: dict | None = None, params: dict | None = None) -> dict:
        """POST request to Rails API."""
        params = {**(params or {}), "session_id": self.session_id}
        url = f"{self.base_url}{path}"
        logger.info("POST %s", url)
        with httpx.Client(timeout=30.0) as client:
            r = client.post(url, params=params, json=body or {}, headers=self.headers)
        if r.status_code >= 400:
            return {"error": f"HTTP {r.status_code}", "detail": r.text}
        return r.json()

    def patch(self, path: str, body: dict | None = None, params: dict | None = None) -> dict:
        """PATCH request to Rails API."""
        params = {**(params or {}), "session_id": self.session_id}
        url = f"{self.base_url}{path}"
        logger.info("PATCH %s", url)
        with httpx.Client(timeout=30.0) as client:
            r = client.patch(url, params=params, json=body or {}, headers=self.headers)
        if r.status_code >= 400:
            return {"error": f"HTTP {r.status_code}", "detail": r.text}
        return r.json()


# ---------------------------------------------------------------------------
# Tool Argument Schemas
# ---------------------------------------------------------------------------

class GetEmailArgs(BaseModel):
    email_id: int = Field(description="The email ID to fetch")

class ListEmailThreadEmailsArgs(BaseModel):
    email_thread_id: int = Field(description="The email thread ID")

class ListLoanProgramsArgs(BaseModel):
    pass

class ListDealsArgs(BaseModel):
    pass

class CreateDealArgs(BaseModel):
    pass

class GetDealArgs(BaseModel):
    id: int = Field(description="The deal ID")

class ListDealRequirementsArgs(BaseModel):
    deal_id: int = Field(description="The deal ID")

class ListDealDocumentsArgs(BaseModel):
    deal_id: int = Field(description="The deal ID")

class UploadDocumentToDealArgs(BaseModel):
    deal_id: int = Field(description="The deal ID")
    file_url: str = Field(description="URL to download the file from")
    filename: str = Field(description="Original filename")

class SearchDealDocumentsArgs(BaseModel):
    deal_id: int = Field(description="The deal ID")
    q: str = Field(description="Search query")
    limit: int | None = Field(None, description="Max results to return")
    threshold: float | None = Field(None, description="Similarity threshold")

class ListDocumentChunksArgs(BaseModel):
    ids: str = Field(description="Comma-separated list of chunk IDs")

class ListOrganizationsArgs(BaseModel):
    pass

class UpdateEmailThreadArgs(BaseModel):
    id: int = Field(description="The email thread ID")
    organization_id: int = Field(description="Organization ID to set")


# ---------------------------------------------------------------------------
# Tool Definitions
# ---------------------------------------------------------------------------

def _make_tools(api: _RailsAPI) -> dict[str, Any]:
    """Create all 13 tools bound to the given API client.

    Returns a dict of {operationId: tool_function}.
    """

    @tool(args_schema=GetEmailArgs)
    def getEmail(email_id: int) -> dict:
        """Fetch email details including attachments and signed download URLs."""
        return api.get(f"/api/v1/emails/{email_id}")

    @tool(args_schema=ListEmailThreadEmailsArgs)
    def listEmailThreadEmails(email_thread_id: int) -> dict:
        """List all emails in a thread."""
        return api.get(f"/api/v1/email_threads/{email_thread_id}/emails")

    @tool(args_schema=ListLoanProgramsArgs)
    def listLoanPrograms() -> dict:
        """List available loan programs."""
        return api.get("/api/v1/loan_programs")

    @tool(args_schema=ListDealsArgs)
    def listDeals() -> dict:
        """List deals accessible to the current session."""
        return api.get("/api/v1/deals")

    @tool(args_schema=CreateDealArgs)
    def createDeal() -> dict:
        """Create a new deal."""
        return api.post("/api/v1/deals")

    @tool(args_schema=GetDealArgs)
    def getDeal(id: int) -> dict:
        """Fetch deal details by ID."""
        return api.get(f"/api/v1/deals/{id}")

    @tool(args_schema=ListDealRequirementsArgs)
    def listDealRequirements(deal_id: int) -> dict:
        """Retrieve all requirements for a deal with accepted document types and assigned documents."""
        return api.get(f"/api/v1/deals/{deal_id}/deal_requirements")

    @tool(args_schema=ListDealDocumentsArgs)
    def listDealDocuments(deal_id: int) -> dict:
        """List all documents associated with a deal."""
        return api.get(f"/api/v1/deals/{deal_id}/documents")

    @tool(args_schema=UploadDocumentToDealArgs)
    def uploadDocumentToDeal(deal_id: int, file_url: str = "", filename: str = "") -> dict:
        """Upload a document to a deal by providing a file URL."""
        body = {"file_url": file_url, "filename": filename}
        return api.post(f"/api/v1/deals/{deal_id}/documents", body=body)

    @tool(args_schema=SearchDealDocumentsArgs)
    def searchDealDocuments(deal_id: int, q: str = "", limit: int | None = None, threshold: float | None = None) -> dict:
        """Search documents within a deal by query text."""
        params = {"q": q}
        if limit is not None:
            params["limit"] = limit
        if threshold is not None:
            params["threshold"] = threshold
        return api.get(f"/api/v1/deals/{deal_id}/search", params=params)

    @tool(args_schema=ListDocumentChunksArgs)
    def listDocumentChunks(ids: str = "") -> dict:
        """Fetch document chunks by IDs."""
        return api.get("/api/v1/document_chunks", params={"ids": ids})

    @tool(args_schema=ListOrganizationsArgs)
    def listOrganizations() -> dict:
        """List organizations accessible to the current session."""
        return api.get("/api/v1/organizations")

    @tool(args_schema=UpdateEmailThreadArgs)
    def updateEmailThread(id: int, organization_id: int = 0) -> dict:
        """Update an email thread (e.g., set organization)."""
        body = {"organization_id": organization_id}
        return api.patch(f"/api/v1/email_threads/{id}", body=body)

    return {
        "getEmail": getEmail,
        "listEmailThreadEmails": listEmailThreadEmails,
        "listLoanPrograms": listLoanPrograms,
        "listDeals": listDeals,
        "createDeal": createDeal,
        "getDeal": getDeal,
        "listDealRequirements": listDealRequirements,
        "listDealDocuments": listDealDocuments,
        "uploadDocumentToDeal": uploadDocumentToDeal,
        "searchDealDocuments": searchDealDocuments,
        "listDocumentChunks": listDocumentChunks,
        "listOrganizations": listOrganizations,
        "updateEmailThread": updateEmailThread,
    }


def get_local_tools(session_id: str, allowed_tools: list[str]) -> list:
    """Get tools for a specific session, filtered to the agent's allowlist.

    Args:
        session_id: Agentic session ID (bound into each tool's API calls)
        allowed_tools: List of operationId strings this agent is allowed to use

    Returns:
        List of LangChain @tool functions matching the allowlist
    """
    api = _RailsAPI(session_id=session_id)
    all_tools = _make_tools(api)

    tools = []
    for name in allowed_tools:
        if name in all_tools:
            tools.append(all_tools[name])
        else:
            logger.warning("Requested tool %s not found in local tools", name)

    logger.info("Loaded %d local tools (of %d requested)", len(tools), len(allowed_tools))
    return tools
```

---

## File 2: `agentic/lois/agents/base_agent.py`

**Change:** Replace the `--- Tools ---` section to skip MCP entirely.

Full copy-paste ready method:

```python
@classmethod
async def get_instance(
    cls, allowed_tools: list[str], system_prompt: str, session_id: str
) -> Self:
    """Create a fresh agent instance with session ID.

    In local mode: ChatAnthropic/ChatOpenAI + hardcoded tools + MemorySaver.
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

    # --- Tools ---
    gateway_url = os.environ.get("GATEWAY_URL", "")
    if not gateway_url:
        from clients.local_rails_tools import get_local_tools

        tools = get_local_tools(session_id=session_id, allowed_tools=allowed_tools)
    else:
        all_tools = await get_gateway_tools(session_id=session_id)
        tools = filter_tools(all_tools, allowed_tools)

    logger.info("%s loaded %d tools", cls.__name__, len(tools))

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

## Environment Variables (Solution C specific)

In addition to [shared env vars](local-dev-shared.md#environment-variables-shared):

```bash
# Agentic .env
GATEWAY_URL=    # empty — triggers local tool mode
```

That's it. Solution C needs the fewest env vars.

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

---

## Tradeoffs

| Pro | Con |
|---|---|
| Simplest mental model — each tool is readable code | Must manually update when Rails API changes |
| Zero dependency on `mcp` library locally | Doesn't exercise `mcp_client.py`, `tool_factory.py`, `schema_converter.py` |
| Easiest to debug — breakpoint on any tool | 13 functions to maintain in sync |
| Fewest moving parts (2 processes) | Low production parity |
| Fastest iteration loop | Tool schemas defined in Python, not from swagger |

---

## Maintenance: Adding a New Endpoint

When a new API endpoint is added to Rails:

1. Add rswag spec and regenerate `swagger.json` (for Solutions A/B)
2. **For Solution C:** Add a new `@tool` function to `local_rails_tools.py`:

```python
class NewToolArgs(BaseModel):
    some_id: int = Field(description="...")

@tool(args_schema=NewToolArgs)
def newOperationId(some_id: int) -> dict:
    """Description matching swagger."""
    return api.get(f"/api/v1/new_endpoint/{some_id}")
```

3. Add the `operationId` to the relevant agent's `ALLOWED_TOOLS` list
4. Add it to the `_make_tools` return dict
