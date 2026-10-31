/* Thin client over the Django/DRF backend. No business logic — the backend
   is authoritative; this only shapes HTTP calls. */

const API_BASE =
  process.env.NEXT_PUBLIC_PAYTRAIL_API ?? "http://localhost:8000/api/agent";

export type ToolEnvelope = {
  ok: boolean;
  data: Record<string, unknown> | null;
  error: { code: string; message: string; retryable: boolean } | null;
  meta: { tool_name: string; request_id: string; observed_at?: string };
};

export type ToolTraceStep = {
  tool_name: string;
  arguments: Record<string, unknown>;
  result: ToolEnvelope;
};

export type ConversationMessage = {
  role: string;
  content?: string;
  tool_calls?: unknown;
  tool_call_id?: string;
};

export type AgentResponse = {
  final_message: string;
  tool_trace: ToolTraceStep[];
  conversation: ConversationMessage[];
};

export type StreamEvent =
  | { type: "tool_result"; tool_name: string; arguments: Record<string, unknown>; result: ToolEnvelope }
  | { type: "final"; final_message: string; conversation: ConversationMessage[] }
  | { type: "error"; error: string };

export type CaseSummary = {
  case_id: string;
  merchant_id: string;
  transaction_id: string | null;
  issue_type: string;
  status: string;
  priority: string;
  assigned_team: string | null;
  summary: string | null;
  created_at: string;
  updated_at: string;
  evidence_refs: string[];
};

export type CaseDetail = {
  case: CaseSummary;
  notes: { note: string; created_at: string }[];
  verifications: {
    verification_scope: string;
    status: string;
    issue_resolved: boolean;
    observed_state: Record<string, unknown>;
    mismatches: string[];
    created_at: string;
  }[];
  device_actions: {
    action_id: string;
    action: string;
    execution_status: string;
    result: Record<string, unknown>;
    executed_at: string;
  }[];
  tool_executions: {
    tool_name: string;
    ok: boolean;
    error_code: string | null;
    result: Record<string, unknown> | null;
    created_at: string;
  }[];
};

async function asJson<T>(response: Response): Promise<T> {
  if (!response.ok) {
    const body = await response.text();
    throw new Error(`${response.status}: ${body.slice(0, 300)}`);
  }
  return response.json() as Promise<T>;
}

export async function sendMessage(
  message: string,
  conversation: ConversationMessage[],
): Promise<AgentResponse> {
  const response = await fetch(`${API_BASE}/message/`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message, conversation }),
  });
  return asJson<AgentResponse>(response);
}

/**
 * Streams one agent turn via SSE: one "tool_result" event per completed tool
 * call, arriving as the agent loop produces them, then a "final" event — not
 * one blocking response after the whole bounded loop finishes. EventSource
 * can't do POST with a body, so this reads the fetch Response stream by hand
 * and splits on SSE "data: ...\n\n" framing.
 */
export async function sendMessageStream(
  message: string,
  conversation: ConversationMessage[],
  onEvent: (event: StreamEvent) => void,
): Promise<void> {
  const response = await fetch(`${API_BASE}/message/stream/`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message, conversation }),
  });
  if (!response.ok || !response.body) {
    const body = await response.text().catch(() => "");
    throw new Error(`${response.status}: ${body.slice(0, 300)}`);
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    const frames = buffer.split("\n\n");
    buffer = frames.pop() ?? "";
    for (const frame of frames) {
      const line = frame.trim();
      if (!line.startsWith("data:")) continue;
      const payload = line.slice("data:".length).trim();
      if (!payload) continue;
      onEvent(JSON.parse(payload) as StreamEvent);
    }
  }
}

export async function transcribe(audio: Blob): Promise<string> {
  const form = new FormData();
  form.append("audio", audio, "audio.webm");
  const response = await fetch(`${API_BASE}/transcribe/`, { method: "POST", body: form });
  const payload = await asJson<{ transcript: string }>(response);
  return payload.transcript;
}

export async function listCases(): Promise<CaseSummary[]> {
  const response = await fetch(`${API_BASE}/cases/`, { cache: "no-store" });
  const payload = await asJson<{ cases: CaseSummary[] }>(response);
  return payload.cases;
}

export async function getCase(caseId: string): Promise<CaseDetail> {
  const response = await fetch(`${API_BASE}/cases/${caseId}/`, { cache: "no-store" });
  return asJson<CaseDetail>(response);
}
