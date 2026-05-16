// AUTO-GENERATED — do not edit by hand. Regenerate via web/scripts/gen-event-types.ts.
// Source of truth: apps/alfred/streaming/events.py

export type UUIDString = string;
export type RunType =
  | "chat_turn" | "llm_call" | "tool_call" | "subagent"
  | "zettel_create" | "writing_compose" | "reading_summarize";
export type ToolResultStatus = "ok" | "error" | "timeout";
export type StateOp = "set" | "append" | "merge" | "remove";

interface EventBase {
  run_id: UUIDString;
  seq: number;
  emitted_at: string;
}

export interface RunStarted extends EventBase {
  event_type: "run.started";
  parent_run_id: UUIDString | null;
  run_type: RunType;
  thread_id: number | null;
  user_id: string | null;
  input_summary: string | null;
  model_id: string | null;
  active_lens: string | null;
}
export interface RunFinished extends EventBase {
  event_type: "run.finished";
  duration_ms: number | null;
  tokens_in: number | null;
  tokens_out: number | null;
  cost_usd: number | null;
}
export interface RunErrored extends EventBase {
  event_type: "run.errored";
  error_type: string;
  error_message: string;
}
export interface RunCancelled extends EventBase {
  event_type: "run.cancelled";
  reason: string | null;
}
export interface MessageStarted extends EventBase {
  event_type: "message.started";
  message_id: UUIDString;
  role: "assistant";
}
export interface MessageDelta extends EventBase {
  event_type: "message.delta";
  message_id: UUIDString;
  delta_text: string;
}
export interface MessageFinished extends EventBase {
  event_type: "message.finished";
  message_id: UUIDString;
  final_text: string;
  token_count: number | null;
}
export interface ThinkingDelta extends EventBase {
  event_type: "thinking.delta";
  message_id: UUIDString;
  delta_text: string;
}
export interface ThinkingFinished extends EventBase {
  event_type: "thinking.finished";
  message_id: UUIDString;
  full_text: string;
}
export interface ToolStarted extends EventBase {
  event_type: "tool.started";
  tool_call_id: UUIDString;
  tool_name: string;
  parent_message_id: UUIDString | null;
  args_preview: Record<string, unknown>;
}
export interface ToolArgsDelta extends EventBase {
  event_type: "tool.args.delta";
  tool_call_id: UUIDString;
  delta_json: string;
}
export interface ToolArgsFinished extends EventBase {
  event_type: "tool.args.finished";
  tool_call_id: UUIDString;
  full_args: Record<string, unknown>;
}
export interface ToolResult extends EventBase {
  event_type: "tool.result";
  tool_call_id: UUIDString;
  message_id: UUIDString | null;
  result_json: Record<string, unknown>;
  duration_ms: number;
  status: ToolResultStatus;
}
export interface StateDelta extends EventBase {
  event_type: "state.delta";
  key: string;
  op: StateOp;
  value: unknown;
}
export interface StateSnapshot extends EventBase {
  event_type: "state.snapshot";
  state: Record<string, unknown>;
}
export interface ProgressUpdate extends EventBase {
  event_type: "progress.update";
  stage: string;
  message: string | null;
  pct_complete: number | null;
}
export interface ApprovalRequired extends EventBase {
  event_type: "approval.required";
  approval_id: UUIDString;
  action: string;
  payload: Record<string, unknown>;
  reason: string | null;
}
export interface ApprovalResolved extends EventBase {
  event_type: "approval.resolved";
  approval_id: UUIDString;
  decision: "approved" | "rejected";
  resolved_by: string | null;
}

export type RunEvent =
  | RunStarted | RunFinished | RunErrored | RunCancelled
  | MessageStarted | MessageDelta | MessageFinished
  | ThinkingDelta | ThinkingFinished
  | ToolStarted | ToolArgsDelta | ToolArgsFinished | ToolResult
  | StateDelta | StateSnapshot
  | ProgressUpdate | ApprovalRequired | ApprovalResolved;
