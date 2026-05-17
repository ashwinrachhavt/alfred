export type StreamEvent = {
  event: string;
  data: Record<string, unknown>;
};

type ToolBuffer = {
  tool: string;
  argsJson: string;
};

type JsonPatch = {
  op?: unknown;
  path?: unknown;
  value?: unknown;
};

const AGUI_EVENT_TYPES = new Set([
  "RUN_STARTED",
  "RUN_FINISHED",
  "RUN_ERROR",
  "TEXT_MESSAGE_START",
  "TEXT_MESSAGE_CONTENT",
  "TEXT_MESSAGE_CHUNK",
  "TEXT_MESSAGE_END",
  "REASONING_MESSAGE_CONTENT",
  "REASONING_MESSAGE_CHUNK",
  "REASONING_MESSAGE_END",
  "TOOL_CALL_START",
  "TOOL_CALL_ARGS",
  "TOOL_CALL_END",
  "TOOL_CALL_RESULT",
  "STATE_SNAPSHOT",
  "STATE_DELTA",
  "ACTIVITY_SNAPSHOT",
  "ACTIVITY_DELTA",
  "CUSTOM",
]);

export function isAguiEvent(event: string): boolean {
  return AGUI_EVENT_TYPES.has(event);
}

export function createAguiEventProjector() {
  const toolBuffers = new Map<string, ToolBuffer>();

  function project(event: string, data: Record<string, unknown>): StreamEvent[] {
    if (!isAguiEvent(event)) return [{ event, data }];

    switch (event) {
      case "RUN_STARTED": {
        const threadId = data.threadId;
        if (threadId === null || threadId === undefined) return [];
        return [{ event: "thread_created", data: { thread_id: Number(threadId) } }];
      }

      case "RUN_FINISHED":
        return [{ event: "done", data: { run_id: data.runId } }];

      case "RUN_ERROR":
        return [{
          event: "error",
          data: { message: String(data.message || data.code || "Something went wrong.") },
        }];

      case "TEXT_MESSAGE_CONTENT":
      case "TEXT_MESSAGE_CHUNK": {
        const delta = typeof data.delta === "string" ? data.delta : "";
        return delta ? [{ event: "token", data: { content: delta } }] : [];
      }

      case "TEXT_MESSAGE_END":
        return [];

      case "REASONING_MESSAGE_CONTENT":
      case "REASONING_MESSAGE_CHUNK": {
        const delta = typeof data.delta === "string" ? data.delta : "";
        return delta ? [{ event: "reasoning", data: { content: delta } }] : [];
      }

      case "REASONING_MESSAGE_END":
        return [];

      case "TOOL_CALL_START": {
        const toolCallId = String(data.toolCallId || "");
        if (!toolCallId) return [];
        toolBuffers.set(toolCallId, {
          tool: String(data.toolCallName || "unknown"),
          argsJson: "",
        });
        return [];
      }

      case "TOOL_CALL_ARGS": {
        const toolCallId = String(data.toolCallId || "");
        const buffered = toolBuffers.get(toolCallId);
        if (!buffered) return [];
        buffered.argsJson += typeof data.delta === "string" ? data.delta : "";
        return [];
      }

      case "TOOL_CALL_END": {
        const toolCallId = String(data.toolCallId || "");
        const buffered = toolBuffers.get(toolCallId);
        if (!buffered) return [];
        toolBuffers.delete(toolCallId);
        return [{
          event: "tool_start",
          data: {
            call_id: toolCallId,
            tool: buffered.tool,
            args: parseJsonObject(buffered.argsJson),
          },
        }];
      }

      case "TOOL_CALL_RESULT": {
        const result = parseToolResult(data.content);
        return [{
          event: "tool_result",
          data: {
            call_id: String(data.toolCallId || ""),
            result,
          },
        }];
      }

      case "STATE_DELTA":
        return projectStateDelta(data.delta);

      case "CUSTOM":
        return projectCustomEvent(data);

      default:
        return [];
    }
  }

  return { project };
}

function parseJsonObject(raw: string): Record<string, unknown> {
  if (!raw.trim()) return {};
  try {
    const parsed = JSON.parse(raw) as unknown;
    return isRecord(parsed) ? parsed : {};
  } catch {
    return {};
  }
}

function parseToolResult(content: unknown): Record<string, unknown> {
  if (isRecord(content)) return content;
  if (typeof content !== "string") return {};
  return parseJsonObject(content);
}

function projectStateDelta(delta: unknown): StreamEvent[] {
  if (!Array.isArray(delta)) return [];
  const events: StreamEvent[] = [];

  for (const patch of delta) {
    if (!isRecord(patch)) continue;
    const { path, value } = patch as JsonPatch;
    if (typeof path !== "string") continue;

    const key = path.split("/").filter(Boolean)[0];
    if (key === "artifacts" && value !== undefined) {
      events.push({ event: "artifact", data: recordOrValue(value) });
    } else if (key === "relatedCards") {
      events.push({ event: "related", data: { cards: Array.isArray(value) ? value : [] } });
    } else if (key === "gaps") {
      events.push({ event: "gaps", data: { gaps: Array.isArray(value) ? value : [] } });
    } else if (key === "pendingApprovals") {
      const actions = Array.isArray(value) ? value : value ? [value] : [];
      events.push({ event: "approval_required", data: { actions } });
    }
  }

  return events;
}

function projectCustomEvent(data: Record<string, unknown>): StreamEvent[] {
  const name = String(data.name || "");
  const value = isRecord(data.value) ? data.value : {};

  if (name.startsWith("alfred.zettel.")) {
    return [{ event: name.slice("alfred.zettel.".length), data: value }];
  }

  if (name.startsWith("alfred.research.")) {
    return [{ event: name.slice("alfred.research.".length), data: value }];
  }

  if (name === "alfred.approval_required") {
    return [{
      event: "approval_required",
      data: {
        actions: [{
          id: String(value.approvalId || ""),
          action: String(value.action || ""),
          reason: String(value.reason || ""),
          payload: isRecord(value.payload) ? value.payload : {},
        }],
      },
    }];
  }

  if (name === "alfred.progress") {
    return [{ event: "progress", data: value }];
  }

  return [];
}

function recordOrValue(value: unknown): Record<string, unknown> {
  return isRecord(value) ? value : { value };
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}
