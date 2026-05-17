"use client";

import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  AlertTriangle,
  CheckCircle2,
  ChevronRight,
  Copy,
  Loader2,
  Play,
  RefreshCw,
  Search,
  ServerCog,
} from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { apiFetch, apiFetchResponse } from "@/lib/api/client";
import { cn, formatErrorMessage, isRecord } from "@/lib/utils";

type HttpMethod = "GET" | "POST" | "PUT" | "PATCH" | "DELETE" | "OPTIONS" | "HEAD" | "TRACE";

type OpenApiParameter = {
  name: string;
  in: "query" | "header" | "path" | "cookie";
  required?: boolean;
  description?: string;
  schema?: unknown;
};

type OpenApiOperation = {
  operationId?: string;
  summary?: string;
  description?: string;
  tags?: string[];
  parameters?: OpenApiParameter[];
  requestBody?: {
    required?: boolean;
    content?: Record<string, { schema?: unknown; example?: unknown; examples?: Record<string, { value?: unknown }> }>;
  };
  responses?: Record<string, { description?: string }>;
};

type OpenApiDocument = {
  openapi?: string;
  info?: { title?: string; version?: string };
  paths?: Record<string, Partial<Record<Lowercase<HttpMethod>, OpenApiOperation>>>;
};

type Endpoint = {
  id: string;
  method: HttpMethod;
  backendPath: string;
  frontendPath: string;
  operation: OpenApiOperation;
  tags: string[];
  label: string;
};

type RequestState = {
  pathValues: Record<string, string>;
  queryValues: Record<string, string>;
  headerValues: Record<string, string>;
  body: string;
};

type ResponseState = {
  status: number;
  statusText: string;
  elapsedMs: number;
  body: string;
  contentType: string;
};

const METHODS: HttpMethod[] = ["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD", "TRACE"];
const BODY_METHODS = new Set<HttpMethod>(["POST", "PUT", "PATCH", "DELETE"]);

function methodTone(method: HttpMethod): string {
  switch (method) {
    case "GET":
      return "border-emerald-500/30 bg-emerald-500/10 text-emerald-300";
    case "POST":
      return "border-sky-500/30 bg-sky-500/10 text-sky-300";
    case "PATCH":
    case "PUT":
      return "border-amber-500/30 bg-amber-500/10 text-amber-300";
    case "DELETE":
      return "border-red-500/30 bg-red-500/10 text-red-300";
    default:
      return "border-muted bg-muted/40 text-muted-foreground";
  }
}

function isHttpMethod(value: string): value is Lowercase<HttpMethod> {
  return METHODS.map((method) => method.toLowerCase()).includes(value as Lowercase<HttpMethod>);
}

function schemaExample(schema: unknown): unknown {
  if (!isRecord(schema)) return {};

  if ("default" in schema) return schema.default;
  if ("example" in schema) return schema.example;

  const type = typeof schema.type === "string" ? schema.type : null;
  if (type === "string") return "string";
  if (type === "integer" || type === "number") return 0;
  if (type === "boolean") return false;
  if (type === "array") return [schemaExample(schema.items)];

  if (type === "object" || isRecord(schema.properties)) {
    const properties = isRecord(schema.properties) ? schema.properties : {};
    return Object.fromEntries(
      Object.entries(properties).map(([key, value]) => [key, schemaExample(value)]),
    );
  }

  if (Array.isArray(schema.anyOf)) return schemaExample(schema.anyOf[0]);
  if (Array.isArray(schema.oneOf)) return schemaExample(schema.oneOf[0]);
  if (Array.isArray(schema.allOf)) return Object.assign({}, ...schema.allOf.map(schemaExample));

  return {};
}

function requestBodyTemplate(operation: OpenApiOperation): string {
  const jsonContent = operation.requestBody?.content?.["application/json"];
  if (!jsonContent) return "";

  const example = jsonContent.example ?? Object.values(jsonContent.examples ?? {})[0]?.value;
  const value = example ?? schemaExample(jsonContent.schema);
  return JSON.stringify(value, null, 2);
}

function normalizeFrontendPath(backendPath: string): string {
  if (backendPath.startsWith("/api/")) return backendPath;
  if (backendPath === "/api") return backendPath;

  const rewritePrefixes = ["/company", "/tasks", "/rag", "/research"];
  const matchedPrefix = rewritePrefixes.find(
    (prefix) => backendPath === prefix || backendPath.startsWith(`${prefix}/`),
  );

  if (!matchedPrefix) return backendPath;
  return `/api${backendPath}`;
}

async function fetchOpenApi(): Promise<OpenApiDocument> {
  return apiFetch<OpenApiDocument>("/api/openapi.json", { cache: "no-store" });
}

function endpointsFromOpenApi(doc: OpenApiDocument): Endpoint[] {
  return Object.entries(doc.paths ?? {}).flatMap(([path, pathItem]) =>
    Object.entries(pathItem).flatMap(([method, operation]) => {
      if (!isHttpMethod(method) || !operation) return [];

      const upperMethod = method.toUpperCase() as HttpMethod;
      const operationTags = operation.tags?.length ? operation.tags : ["untagged"];
      const label = operation.summary || operation.operationId || `${upperMethod} ${path}`;

      return [
        {
          id: `${upperMethod} ${path}`,
          method: upperMethod,
          backendPath: path,
          frontendPath: normalizeFrontendPath(path),
          operation,
          tags: operationTags,
          label,
        },
      ];
    }),
  );
}

function paramsFor(endpoint: Endpoint, location: OpenApiParameter["in"]): OpenApiParameter[] {
  return endpoint.operation.parameters?.filter((param) => param.in === location) ?? [];
}

function initialRequestState(endpoint: Endpoint): RequestState {
  const pathValues = Object.fromEntries(
    paramsFor(endpoint, "path").map((param) => [param.name, `{${param.name}}`]),
  );
  const queryValues = Object.fromEntries(paramsFor(endpoint, "query").map((param) => [param.name, ""]));
  const headerValues = Object.fromEntries(
    paramsFor(endpoint, "header").map((param) => [param.name, ""]),
  );

  return {
    pathValues,
    queryValues,
    headerValues,
    body: requestBodyTemplate(endpoint.operation),
  };
}

function buildRequestUrl(endpoint: Endpoint, state: RequestState): string {
  let path = endpoint.frontendPath;
  for (const [name, value] of Object.entries(state.pathValues)) {
    path = path.replace(`{${name}}`, encodeURIComponent(value));
  }

  const query = new URLSearchParams();
  for (const [name, value] of Object.entries(state.queryValues)) {
    if (value.trim()) query.set(name, value.trim());
  }

  const queryString = query.toString();
  return queryString ? `${path}?${queryString}` : path;
}

function formatResponseBody(body: string, contentType: string): string {
  if (!body) return "No response body";
  if (!contentType.includes("application/json")) return body;

  try {
    return JSON.stringify(JSON.parse(body), null, 2);
  } catch {
    return body;
  }
}

function endpointSearchText(endpoint: Endpoint): string {
  return [
    endpoint.id,
    endpoint.label,
    endpoint.operation.description,
    endpoint.operation.operationId,
    endpoint.tags.join(" "),
  ]
    .filter(Boolean)
    .join(" ")
    .toLowerCase();
}

function ParameterInputs({
  title,
  params,
  values,
  onChange,
}: {
  title: string;
  params: OpenApiParameter[];
  values: Record<string, string>;
  onChange: (next: Record<string, string>) => void;
}) {
  if (params.length === 0) return null;

  return (
    <div className="space-y-2">
      <h3 className="label-mono text-[var(--alfred-text-tertiary)]">{title}</h3>
      <div className="grid gap-2 md:grid-cols-2">
        {params.map((param) => (
          <label key={`${param.in}-${param.name}`} className="space-y-1">
            <span className="flex items-center gap-1 text-[11px] font-medium tracking-wide uppercase text-muted-foreground">
              {param.name}
              {param.required ? <span className="text-primary">required</span> : null}
            </span>
            <Input
              value={values[param.name] ?? ""}
              onChange={(event) => onChange({ ...values, [param.name]: event.target.value })}
              placeholder={param.description ?? param.name}
              className="font-mono text-xs"
            />
          </label>
        ))}
      </div>
    </div>
  );
}

function EndpointPanel({ endpoint }: { endpoint: Endpoint }) {
  const [request, setRequest] = useState(() => initialRequestState(endpoint));
  const [response, setResponse] = useState<ResponseState | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isRunning, setIsRunning] = useState(false);

  const pathParams = paramsFor(endpoint, "path");
  const queryParams = paramsFor(endpoint, "query");
  const headerParams = paramsFor(endpoint, "header");
  const hasBody = Boolean(endpoint.operation.requestBody) || BODY_METHODS.has(endpoint.method);
  const requestUrl = buildRequestUrl(endpoint, request);

  const runEndpoint = async () => {
    setIsRunning(true);
    setError(null);
    setResponse(null);

    try {
      const headers = new Headers();
      for (const [name, value] of Object.entries(request.headerValues)) {
        if (value.trim()) headers.set(name, value.trim());
      }

      const init: RequestInit = { method: endpoint.method, headers };
      if (hasBody && request.body.trim()) {
        headers.set("content-type", headers.get("content-type") ?? "application/json");
        init.body = request.body;
      }

      const startedAt = performance.now();
      const result = await apiFetchResponse(requestUrl, init);
      const body = await result.text();
      setResponse({
        status: result.status,
        statusText: result.statusText,
        elapsedMs: Math.round(performance.now() - startedAt),
        body: formatResponseBody(body, result.headers.get("content-type") ?? ""),
        contentType: result.headers.get("content-type") ?? "unknown",
      });
    } catch (caught) {
      setError(formatErrorMessage(caught));
    } finally {
      setIsRunning(false);
    }
  };

  const resetRequest = () => {
    setRequest(initialRequestState(endpoint));
    setResponse(null);
    setError(null);
  };

  return (
    <Card className="overflow-hidden border-primary/15">
      <CardHeader className="gap-4 border-b pb-5">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="min-w-0 space-y-2">
            <div className="flex flex-wrap items-center gap-2">
              <Badge variant="outline" className={cn("rounded-sm font-mono text-[10px]", methodTone(endpoint.method))}>
                {endpoint.method}
              </Badge>
              {endpoint.tags.map((tag) => (
                <Badge key={tag} variant="secondary" className="rounded-sm text-[10px] uppercase tracking-wide">
                  {tag}
                </Badge>
              ))}
            </div>
            <CardTitle className="font-serif text-2xl font-normal tracking-tight">
              {endpoint.label}
            </CardTitle>
            <p className="break-all font-mono text-xs text-muted-foreground">{endpoint.backendPath}</p>
          </div>
          <div className="flex gap-2">
            <Button type="button" variant="outline" size="sm" onClick={resetRequest}>
              Reset
            </Button>
            <Button type="button" size="sm" onClick={() => void runEndpoint()} disabled={isRunning}>
              {isRunning ? <Loader2 className="size-4 animate-spin" /> : <Play className="size-4" />}
              Run
            </Button>
          </div>
        </div>
        {endpoint.operation.description ? (
          <p className="text-sm leading-6 text-muted-foreground">{endpoint.operation.description}</p>
        ) : null}
      </CardHeader>

      <CardContent className="space-y-6 p-5">
        <div className="rounded-md border bg-muted/20 p-3">
          <div className="label-mono mb-2 text-[var(--alfred-text-tertiary)]">Request URL</div>
          <code className="break-all font-mono text-xs text-foreground">{requestUrl}</code>
        </div>

        <ParameterInputs
          title="Path parameters"
          params={pathParams}
          values={request.pathValues}
          onChange={(pathValues) => setRequest((current) => ({ ...current, pathValues }))}
        />
        <ParameterInputs
          title="Query parameters"
          params={queryParams}
          values={request.queryValues}
          onChange={(queryValues) => setRequest((current) => ({ ...current, queryValues }))}
        />
        <ParameterInputs
          title="Headers"
          params={headerParams}
          values={request.headerValues}
          onChange={(headerValues) => setRequest((current) => ({ ...current, headerValues }))}
        />

        {hasBody ? (
          <div className="space-y-2">
            <h3 className="label-mono text-[var(--alfred-text-tertiary)]">JSON body</h3>
            <Textarea
              value={request.body}
              onChange={(event) => setRequest((current) => ({ ...current, body: event.target.value }))}
              className="min-h-44 font-mono text-xs leading-5"
              placeholder="{}"
            />
          </div>
        ) : null}

        {error ? (
          <div className="flex gap-2 border-l-3 border-red-500 bg-red-500/8 p-3 text-sm text-red-300">
            <AlertTriangle className="mt-0.5 size-4 shrink-0" />
            {error}
          </div>
        ) : null}

        {response ? (
          <div className="space-y-3">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div className="flex items-center gap-2">
                {response.status >= 200 && response.status < 300 ? (
                  <CheckCircle2 className="size-4 text-emerald-400" />
                ) : (
                  <AlertTriangle className="size-4 text-amber-400" />
                )}
                <span className="font-mono text-xs">
                  {response.status} {response.statusText} · {response.elapsedMs}ms
                </span>
              </div>
              <Button
                type="button"
                variant="ghost"
                size="sm"
                onClick={() => void navigator.clipboard.writeText(response.body)}
              >
                <Copy className="size-4" />
                Copy
              </Button>
            </div>
            <pre className="max-h-[520px] overflow-auto rounded-md border bg-black/20 p-4 text-xs leading-5 text-muted-foreground">
              {response.body}
            </pre>
            <p className="font-mono text-[10px] text-[var(--alfred-text-tertiary)]">
              Content-Type: {response.contentType}
            </p>
          </div>
        ) : null}
      </CardContent>
    </Card>
  );
}

export default function ApiWorkbenchPage() {
  const [query, setQuery] = useState("");
  const [selectedTag, setSelectedTag] = useState("all");
  const [selectedMethod, setSelectedMethod] = useState<HttpMethod | "all">("all");
  const openApiQuery = useQuery({ queryKey: ["openapi"], queryFn: fetchOpenApi });

  const endpoints = useMemo(
    () => (openApiQuery.data ? endpointsFromOpenApi(openApiQuery.data) : []),
    [openApiQuery.data],
  );

  const tags = useMemo(
    () => ["all", ...Array.from(new Set(endpoints.flatMap((endpoint) => endpoint.tags))).sort()],
    [endpoints],
  );

  const filteredEndpoints = useMemo(() => {
    const needle = query.trim().toLowerCase();
    return endpoints.filter((endpoint) => {
      const tagMatches = selectedTag === "all" || endpoint.tags.includes(selectedTag);
      const methodMatches = selectedMethod === "all" || endpoint.method === selectedMethod;
      const searchMatches = !needle || endpointSearchText(endpoint).includes(needle);
      return tagMatches && methodMatches && searchMatches;
    });
  }, [endpoints, query, selectedMethod, selectedTag]);

  const [selectedEndpointId, setSelectedEndpointId] = useState<string | null>(null);
  const selectedEndpoint =
    filteredEndpoints.find((endpoint) => endpoint.id === selectedEndpointId) ?? filteredEndpoints[0] ?? null;

  return (
    <div className="min-h-full bg-background">
      <div className="border-b bg-card/40">
        <div className="mx-auto flex max-w-7xl flex-col gap-5 px-6 py-8">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div>
              <div className="mb-3 flex items-center gap-2 text-primary">
                <ServerCog className="size-5" />
                <span className="label-mono">Backend coverage</span>
              </div>
              <h1 className="font-serif text-4xl tracking-tight">API Workbench</h1>
              <p className="mt-2 max-w-2xl text-sm leading-6 text-muted-foreground">
                A generated frontend for every FastAPI operation. It reads the live OpenAPI schema, so new backend functions appear here automatically.
              </p>
            </div>
            <Button
              type="button"
              variant="outline"
              onClick={() => void openApiQuery.refetch()}
              disabled={openApiQuery.isFetching}
            >
              <RefreshCw className={cn("size-4", openApiQuery.isFetching && "animate-spin")} />
              Refresh schema
            </Button>
          </div>

          <div className="grid gap-3 sm:grid-cols-3">
            <div className="rounded-lg border bg-card p-4">
              <div className="font-serif text-3xl text-primary">{endpoints.length}</div>
              <div className="label-mono mt-1 text-[var(--alfred-text-tertiary)]">Operations</div>
            </div>
            <div className="rounded-lg border bg-card p-4">
              <div className="font-serif text-3xl text-primary">{tags.length - 1}</div>
              <div className="label-mono mt-1 text-[var(--alfred-text-tertiary)]">Backend modules</div>
            </div>
            <div className="rounded-lg border bg-card p-4">
              <div className="font-serif text-3xl text-primary">
                {openApiQuery.data?.info?.version ?? openApiQuery.data?.openapi ?? "—"}
              </div>
              <div className="label-mono mt-1 text-[var(--alfred-text-tertiary)]">Schema version</div>
            </div>
          </div>
        </div>
      </div>

      <div className="mx-auto grid max-w-7xl gap-6 px-6 py-6 lg:grid-cols-[360px_1fr]">
        <aside className="space-y-4 lg:sticky lg:top-4 lg:self-start">
          <div className="relative">
            <Search className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-muted-foreground" />
            <Input
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Search endpoints"
              className="pl-9"
            />
          </div>

          <div className="flex flex-wrap gap-2">
            {(["all", ...METHODS] as Array<HttpMethod | "all">).map((method) => (
              <button
                key={method}
                type="button"
                onClick={() => setSelectedMethod(method)}
                className={cn(
                  "rounded-sm border px-2 py-1 font-mono text-[10px] tracking-wide uppercase transition-colors",
                  selectedMethod === method
                    ? "border-primary bg-[var(--alfred-accent-subtle)] text-primary"
                    : "border-border text-muted-foreground hover:bg-[var(--alfred-accent-subtle)] hover:text-foreground",
                )}
              >
                {method}
              </button>
            ))}
          </div>

          <select
            value={selectedTag}
            onChange={(event) => setSelectedTag(event.target.value)}
            className="border-input bg-background h-9 w-full rounded-md border px-3 text-sm"
          >
            {tags.map((tag) => (
              <option key={tag} value={tag}>
                {tag === "all" ? "All backend modules" : tag}
              </option>
            ))}
          </select>

          <div className="max-h-[65vh] overflow-auto rounded-lg border bg-card/50">
            {openApiQuery.isLoading ? (
              <div className="flex items-center gap-2 p-4 text-sm text-muted-foreground">
                <Loader2 className="size-4 animate-spin" />
                Loading schema
              </div>
            ) : null}
            {openApiQuery.error ? (
              <div className="border-l-3 border-red-500 bg-red-500/8 p-4 text-sm text-red-300">
                {formatErrorMessage(openApiQuery.error)}
              </div>
            ) : null}
            {filteredEndpoints.map((endpoint) => (
              <button
                key={endpoint.id}
                type="button"
                onClick={() => setSelectedEndpointId(endpoint.id)}
                className={cn(
                  "flex w-full items-start gap-3 border-b p-3 text-left transition-colors last:border-b-0",
                  selectedEndpoint?.id === endpoint.id
                    ? "bg-[var(--alfred-accent-subtle)]"
                    : "hover:bg-[var(--alfred-accent-subtle)]/70",
                )}
              >
                <Badge variant="outline" className={cn("rounded-sm font-mono text-[10px]", methodTone(endpoint.method))}>
                  {endpoint.method}
                </Badge>
                <span className="min-w-0 flex-1">
                  <span className="block truncate text-sm font-medium">{endpoint.label}</span>
                  <span className="mt-1 block truncate font-mono text-[11px] text-muted-foreground">
                    {endpoint.backendPath}
                  </span>
                </span>
                <ChevronRight className="mt-1 size-3 shrink-0 text-muted-foreground" />
              </button>
            ))}
            {!openApiQuery.isLoading && filteredEndpoints.length === 0 ? (
              <div className="p-4 text-sm text-muted-foreground">No endpoints match the current filters.</div>
            ) : null}
          </div>
        </aside>

        <main>{selectedEndpoint ? <EndpointPanel key={selectedEndpoint.id} endpoint={selectedEndpoint} /> : null}</main>
      </div>
    </div>
  );
}
