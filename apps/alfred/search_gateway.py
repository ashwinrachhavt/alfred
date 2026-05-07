"""Local search infrastructure gateway for Alfred development.

This app exposes the `localhost:8010` contract used by local agent tooling while
reusing Alfred's Docker services instead of requiring a second conflicting stack.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import httpx
from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel

from alfred.core.settings import settings

app = FastAPI(title="Alfred Search Gateway", version="1.0.0")


class MeiliAddDocumentsRequest(BaseModel):
    index: str
    documents: list[dict[str, Any]]
    primary_key: str | None = None


class MeiliSearchRequest(BaseModel):
    index: str
    query: str
    limit: int | None = None
    offset: int | None = None
    filter: str | None = None
    sort: list[str] | None = None
    attributes_to_retrieve: list[str] | None = None


class MeiliCreateIndexRequest(BaseModel):
    uid: str
    primary_key: str | None = None


class LiteLLMChatRequest(BaseModel):
    model: str = "gpt-4o-mini"
    messages: list[dict[str, Any]]
    temperature: float | None = None
    max_tokens: int | None = None


class LiteLLMEmbeddingRequest(BaseModel):
    model: str
    input: str | list[str]


def _url(value: str | None, default: str) -> str:
    return (value or default).rstrip("/")


def _service_urls() -> dict[str, str]:
    return {
        "firecrawl": _url(settings.search_gateway_firecrawl_url, settings.firecrawl_base_url),
        "searxng": _url(
            settings.search_gateway_searxng_url,
            settings.searxng_host or settings.searx_host or "http://localhost:8090",
        ),
        "qdrant": _url(
            settings.search_gateway_qdrant_url,
            settings.qdrant_local_url or settings.qdrant_url or "http://localhost:6333",
        ),
        "meilisearch": _url(settings.search_gateway_meilisearch_url, "http://localhost:7700"),
        "tika": _url(settings.search_gateway_tika_url, "http://localhost:9998"),
        "litellm": _url(settings.search_gateway_litellm_url, "http://localhost:4000"),
        "gotenberg": _url(settings.search_gateway_gotenberg_url, "http://localhost:3030"),
        "n8n": _url(settings.search_gateway_n8n_url, "http://localhost:5678"),
    }


async def _check(client: httpx.AsyncClient, url: str) -> str:
    try:
        response = await client.get(url, timeout=3)
    except httpx.HTTPError:
        return "down"
    return "up" if response.status_code < 500 else "error"


@app.get("/health")
async def health() -> dict[str, Any]:
    urls = _service_urls()
    statuses: dict[str, Any] = {
        "firecrawl_url": urls["firecrawl"],
        "searxng_url": urls["searxng"],
        "qdrant_url": urls["qdrant"],
        "meilisearch_url": urls["meilisearch"],
        "tika_url": urls["tika"],
        "litellm_url": urls["litellm"],
        "gotenberg_url": urls["gotenberg"],
        "n8n_url": urls["n8n"],
    }
    async with httpx.AsyncClient() as client:
        checks = {
            "firecrawl": urls["firecrawl"],
            "searxng": urls["searxng"],
            "qdrant": f"{urls['qdrant']}/healthz",
            "meilisearch": f"{urls['meilisearch']}/health",
            "tika": urls["tika"],
            "litellm": f"{urls['litellm']}/health",
            "gotenberg": f"{urls['gotenberg']}/health",
            "n8n": f"{urls['n8n']}/healthz",
        }
        for name, url in checks.items():
            statuses[f"{name}_status"] = await _check(client, url)
    return statuses


def _clean_headers(headers: Mapping[str, str]) -> dict[str, str]:
    excluded = {"host", "content-length", "connection"}
    return {key: value for key, value in headers.items() if key.lower() not in excluded}


def _meili_headers() -> dict[str, str]:
    return {
        "Authorization": f"Bearer {settings.search_gateway_meilisearch_key}",
        "Content-Type": "application/json",
    }


def _litellm_headers() -> dict[str, str]:
    headers = {"Content-Type": "application/json"}
    if settings.search_gateway_litellm_key:
        headers["Authorization"] = f"Bearer {settings.search_gateway_litellm_key}"
    return headers


def _json_or_text(response: httpx.Response) -> Any:
    try:
        return response.json()
    except ValueError:
        return response.text


async def _proxy(request: Request, base_url: str, path: str) -> Response:
    body = await request.body()
    url = f"{base_url.rstrip('/')}/{path.lstrip('/')}"
    async with httpx.AsyncClient(timeout=300) as client:
        upstream = await client.request(
            request.method,
            url,
            content=body if body else None,
            headers=_clean_headers(request.headers),
            params=request.query_params,
        )
    return Response(
        content=upstream.content,
        status_code=upstream.status_code,
        media_type=upstream.headers.get("content-type"),
    )


@app.api_route("/firecrawl/{path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE"])
async def firecrawl_proxy(path: str, request: Request) -> Response:
    return await _proxy(request, _service_urls()["firecrawl"], path)


@app.api_route("/qdrant/{path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE"])
async def qdrant_proxy(path: str, request: Request) -> Response:
    return await _proxy(request, _service_urls()["qdrant"], path)


@app.post("/meili/indexes")
async def meili_create_index(req: MeiliCreateIndexRequest) -> dict[str, Any]:
    body: dict[str, Any] = {"uid": req.uid}
    if req.primary_key:
        body["primaryKey"] = req.primary_key
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.post(
            f"{_service_urls()['meilisearch']}/indexes",
            headers=_meili_headers(),
            json=body,
        )
    return {"success": response.status_code < 300, "data": _json_or_text(response)}


@app.get("/meili/indexes")
async def meili_list_indexes() -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.get(
            f"{_service_urls()['meilisearch']}/indexes",
            headers=_meili_headers(),
        )
    return {"success": response.status_code < 300, "data": _json_or_text(response)}


@app.post("/meili/documents")
async def meili_add_documents(req: MeiliAddDocumentsRequest) -> dict[str, Any]:
    url = f"{_service_urls()['meilisearch']}/indexes/{req.index}/documents"
    params = {"primaryKey": req.primary_key} if req.primary_key else None
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.post(
            url,
            headers=_meili_headers(),
            params=params,
            json=req.documents,
        )
    return {"success": response.status_code < 300, "data": _json_or_text(response)}


@app.post("/meili/search")
async def meili_search(req: MeiliSearchRequest) -> dict[str, Any]:
    body: dict[str, Any] = {"q": req.query}
    if req.limit is not None:
        body["limit"] = req.limit
    if req.offset is not None:
        body["offset"] = req.offset
    if req.filter:
        body["filter"] = req.filter
    if req.sort:
        body["sort"] = req.sort
    if req.attributes_to_retrieve:
        body["attributesToRetrieve"] = req.attributes_to_retrieve
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.post(
            f"{_service_urls()['meilisearch']}/indexes/{req.index}/search",
            headers=_meili_headers(),
            json=body,
        )
    return {"success": response.status_code < 300, "data": _json_or_text(response)}


@app.post("/tika/parse")
async def tika_parse(
    file: UploadFile = File(...),
    output_format: str = Form("text"),
) -> dict[str, Any]:
    content = await file.read()
    content_type = file.content_type or "application/octet-stream"
    endpoint = "/meta" if output_format == "metadata" else "/tika"
    accept = "application/json" if output_format == "metadata" else "text/plain"
    if output_format == "html":
        accept = "text/html"
    async with httpx.AsyncClient(timeout=120) as client:
        response = await client.put(
            f"{_service_urls()['tika']}{endpoint}",
            content=content,
            headers={"Content-Type": content_type, "Accept": accept},
        )
    if response.status_code >= 400:
        raise HTTPException(status_code=response.status_code, detail=response.text)
    data = response.json() if output_format == "metadata" else {
        "content": response.text,
        "format": output_format,
    }
    return {"success": True, "data": data}


@app.get("/llm/models")
async def llm_models() -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.get(
            f"{_service_urls()['litellm']}/models",
            headers=_litellm_headers(),
        )
    return {"success": response.status_code < 300, "data": _json_or_text(response)}


@app.post("/llm/chat")
async def llm_chat(req: LiteLLMChatRequest) -> dict[str, Any]:
    body: dict[str, Any] = {"model": req.model, "messages": req.messages, "stream": False}
    if req.temperature is not None:
        body["temperature"] = req.temperature
    if req.max_tokens is not None:
        body["max_tokens"] = req.max_tokens
    async with httpx.AsyncClient(timeout=120) as client:
        response = await client.post(
            f"{_service_urls()['litellm']}/chat/completions",
            headers=_litellm_headers(),
            json=body,
        )
    if response.status_code >= 400:
        raise HTTPException(status_code=response.status_code, detail=response.text)
    return {"success": True, "data": response.json()}


@app.post("/llm/embeddings")
async def llm_embeddings(req: LiteLLMEmbeddingRequest) -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=60) as client:
        response = await client.post(
            f"{_service_urls()['litellm']}/embeddings",
            headers=_litellm_headers(),
            json={"model": req.model, "input": req.input},
        )
    if response.status_code >= 400:
        raise HTTPException(status_code=response.status_code, detail=response.text)
    return {"success": True, "data": response.json()}


@app.post("/gotenberg/html-to-pdf")
async def gotenberg_html_to_pdf(file: UploadFile = File(...)) -> dict[str, Any]:
    import base64

    content = await file.read()
    async with httpx.AsyncClient(timeout=60) as client:
        response = await client.post(
            f"{_service_urls()['gotenberg']}/forms/chromium/convert/html",
            files={"files": ("index.html", content, "text/html")},
        )
    if response.status_code >= 400:
        raise HTTPException(status_code=response.status_code, detail=response.text)
    return {
        "success": True,
        "data": {
            "pdf_base64": base64.b64encode(response.content).decode(),
            "size_bytes": len(response.content),
        },
    }


@app.post("/gotenberg/url-to-pdf")
async def gotenberg_url_to_pdf(url: str = Form(...)) -> dict[str, Any]:
    import base64

    async with httpx.AsyncClient(timeout=60) as client:
        response = await client.post(
            f"{_service_urls()['gotenberg']}/forms/chromium/convert/url",
            files={"url": (None, url)},
        )
    if response.status_code >= 400:
        raise HTTPException(status_code=response.status_code, detail=response.text)
    return {
        "success": True,
        "data": {
            "pdf_base64": base64.b64encode(response.content).decode(),
            "size_bytes": len(response.content),
        },
    }


@app.api_route("/meili/raw/{path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE"])
async def meili_raw_proxy(path: str, request: Request) -> Response:
    return await _proxy(request, _service_urls()["meilisearch"], path)


@app.api_route("/searxng/{path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE"])
async def searxng_proxy(path: str, request: Request) -> Response:
    return await _proxy(request, _service_urls()["searxng"], path)
