"use client";

import { useRef, useState } from "react";
import Link from "next/link";
import {
  Check,
  DoubleCheck,
  Mic,
  Send,
  StatusIcon,
  Stop,
} from "@/components/Icons";
import {
  sendMessageStream,
  transcribe,
  type ConversationMessage,
  type ToolTraceStep,
} from "@/lib/api";

/* Merchant-facing phrasing — a real merchant never sees a raw snake_case
   tool name. The support dashboard shows the real names instead. */
const FRIENDLY_TOOL_LABELS: Record<string, string> = {
  investigate_payment_case: "Checked the payment and related records",
  search_support_knowledge: "Looked up relevant support guidance",
  inspect_device: "Inspected the Soundbox device",
  execute_device_action: "Ran a device diagnostic",
  manage_support_case: "Updated the support case",
  verify_case_outcome: "Verified the current status",
  notify_merchant: "Sent you an update",
};

const SCENARIOS = [
  {
    chip: "Soundbox didn't beep",
    preset:
      "Main M100 se bol raha hoon. Customer ne TXN1002 ka payment kiya, lekin Soundbox nahi bola.",
  },
  {
    chip: "Payment stuck on pending",
    preset: "Mera M102 ka payment TXN2001 abhi tak pending dikha raha hai.",
  },
  {
    chip: "Customer says money was deducted",
    preset:
      "M103 ka transaction TXN3001 fail hua bola, lekin customer bol raha paise kat gaye.",
  },
];

const LANGUAGES = ["en", "hi", "mr"] as const;

type Kind = "ok" | "warn" | "err";

type Entry =
  | { role: "merchant"; text: string; time: string }
  | { role: "agent"; text: string; time: string }
  | { role: "progress"; text: string; ok: boolean }
  | { role: "error"; text: string };

type StatusState = {
  paymentStatus?: string;
  paymentAmount?: number;
  deviceOnline?: boolean;
  caseId?: string;
  caseStatus?: string;
  assignedTeam?: string | null;
};

const TINTS: Record<Kind, { bg: string; fg: string }> = {
  ok: { bg: "var(--teal-tint-bg)", fg: "var(--teal-tint-text)" },
  warn: { bg: "var(--orange-tint-bg)", fg: "var(--orange-tint-text)" },
  err: { bg: "var(--red-tint-bg)", fg: "var(--red-tint-text)" },
};

function nowLabel() {
  return new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

function deriveStatus(prev: StatusState, trace: ToolTraceStep[]): StatusState {
  const next = { ...prev };
  for (const step of trace) {
    if (!step.result.ok || !step.result.data) continue;
    const data = step.result.data as Record<string, any>;
    if (step.tool_name === "investigate_payment_case") {
      if (data.transaction) {
        next.paymentStatus = data.transaction.status;
        next.paymentAmount = data.transaction.amount;
      }
      if (data.device_summary) next.deviceOnline = data.device_summary.online;
    } else if (step.tool_name === "inspect_device") {
      if (data.connectivity) next.deviceOnline = data.connectivity.online;
    } else if (step.tool_name === "execute_device_action") {
      const result = data.result as Record<string, any> | null;
      if (result && "device_reachable" in result) next.deviceOnline = result.device_reachable;
      else if (result && "online" in result) next.deviceOnline = result.online;
    } else if (step.tool_name === "manage_support_case") {
      next.caseId = data.case_id;
      next.caseStatus = data.status;
      next.assignedTeam = data.assigned_team;
    }
  }
  return next;
}

export default function MerchantChat() {
  const [entries, setEntries] = useState<Entry[]>([]);
  const [conversation, setConversation] = useState<ConversationMessage[]>([]);
  const [status, setStatus] = useState<StatusState>({});
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [recording, setRecording] = useState(false);
  const [lang, setLang] = useState<string>("en");

  const recorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);

  async function runTurn(message: string) {
    if (!message.trim() || busy) return;
    setBusy(true);
    setEntries((prev) => [...prev, { role: "merchant", text: message, time: nowLabel() }]);
    try {
      // Streamed: each progress line and the status strip update live, the
      // moment that specific tool call finishes — not held back until the
      // whole bounded loop completes.
      await sendMessageStream(message, conversation, (event) => {
        if (event.type === "tool_result") {
          const step: ToolTraceStep = { tool_name: event.tool_name, arguments: event.arguments, result: event.result };
          setStatus((prev) => deriveStatus(prev, [step]));
          setEntries((prev) => [
            ...prev,
            { role: "progress", text: FRIENDLY_TOOL_LABELS[event.tool_name] ?? event.tool_name, ok: event.result.ok },
          ]);
        } else if (event.type === "final") {
          setConversation(event.conversation);
          setEntries((prev) => [...prev, { role: "agent", text: event.final_message, time: nowLabel() }]);
        } else {
          setEntries((prev) => [...prev, { role: "error", text: `Agent error: ${event.error}` }]);
        }
      });
    } catch (error) {
      setEntries((prev) => [
        ...prev,
        { role: "error", text: `Couldn't reach PayTrail: ${(error as Error).message}` },
      ]);
    } finally {
      setBusy(false);
    }
  }

  async function startRecording() {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const recorder = new MediaRecorder(stream);
      chunksRef.current = [];
      recorder.ondataavailable = (event) => {
        if (event.data.size > 0) chunksRef.current.push(event.data);
      };
      recorder.onstop = async () => {
        stream.getTracks().forEach((track) => track.stop());
        const blob = new Blob(chunksRef.current, { type: "audio/webm" });
        setBusy(true);
        try {
          const transcript = await transcribe(blob);
          setBusy(false);
          await runTurn(transcript);
        } catch (error) {
          setBusy(false);
          setEntries((prev) => [
            ...prev,
            { role: "error", text: `Speech-to-text failed: ${(error as Error).message}` },
          ]);
        }
      };
      recorder.start();
      recorderRef.current = recorder;
      setRecording(true);
    } catch (error) {
      setEntries((prev) => [
        ...prev,
        { role: "error", text: `Microphone unavailable: ${(error as Error).message}` },
      ]);
    }
  }

  function stopRecording() {
    recorderRef.current?.stop();
    recorderRef.current = null;
    setRecording(false);
  }

  const badges: { label: string; kind: Kind }[] = [];
  if (status.paymentStatus) {
    const kindMap: Record<string, Kind> = { SUCCESS: "ok", PENDING: "warn", FAILED: "err" };
    const kind = kindMap[status.paymentStatus] ?? "warn";
    const amount =
      status.paymentAmount !== undefined
        ? `₹${status.paymentAmount.toLocaleString("en-IN", { minimumFractionDigits: 2 })} `
        : "";
    badges.push({
      label: `${amount}${status.paymentStatus === "SUCCESS" ? "received" : status.paymentStatus.toLowerCase()}`,
      kind,
    });
  }
  if (status.deviceOnline !== undefined) {
    badges.push({
      label: status.deviceOnline ? "Soundbox online" : "Soundbox offline",
      kind: status.deviceOnline ? "ok" : "warn",
    });
  }
  if (status.caseStatus) {
    const kindMap: Record<string, Kind> = { RESOLVED: "ok", ESCALATED: "err" };
    badges.push({
      label: `Case ${status.caseId ?? ""} · ${status.assignedTeam ?? status.caseStatus}`,
      kind: kindMap[status.caseStatus] ?? "warn",
    });
  }

  return (
    <div style={{ minHeight: "100vh", display: "flex", flexDirection: "column" }}>
      {/* Header */}
      <div
        style={{
          display: "flex",
          flexWrap: "wrap",
          gap: 16,
          alignItems: "center",
          justifyContent: "space-between",
          padding: "18px 32px",
          borderBottom: "1px solid var(--border)",
          background: "linear-gradient(180deg,#0e2037,#0b1a2e)",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <div className="brandMark">P</div>
          <div>
            <div style={{ fontWeight: 800, fontSize: 16 }}>PayTrail</div>
            <div style={{ display: "flex", alignItems: "center", gap: 5, fontSize: 11, color: "var(--text-muted)" }}>
              <span
                style={{
                  width: 6,
                  height: 6,
                  borderRadius: "50%",
                  background: "var(--teal)",
                  boxShadow: "0 0 0 3px rgba(45,212,191,0.15)",
                }}
              />
              Active now · replies in seconds
            </div>
          </div>
        </div>

        <div style={{ display: "flex", alignItems: "center", gap: 14 }}>
          <Link href="/dashboard" className="navLink">
            Support dashboard
          </Link>
          <div style={{ display: "flex", gap: 6 }}>
            {LANGUAGES.map((code) => (
              <button
                key={code}
                onClick={() => setLang(code)}
                style={{
                  padding: "6px 11px",
                  borderRadius: 8,
                  border: "1px solid var(--border)",
                  fontSize: 11.5,
                  fontWeight: 700,
                  background: lang === code ? "var(--teal)" : "transparent",
                  color: lang === code ? "var(--teal-deep)" : "var(--text-muted)",
                }}
              >
                {code.toUpperCase()}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Scenario chips */}
      <div style={{ padding: "18px 32px 0 32px" }}>
        <div
          style={{
            fontSize: 11,
            fontWeight: 700,
            color: "var(--text-faint)",
            textTransform: "uppercase",
            letterSpacing: 0.7,
            marginBottom: 10,
          }}
        >
          Try a conversation
        </div>
        <div style={{ display: "flex", flexWrap: "wrap", gap: 10 }}>
          {SCENARIOS.map((scenario) => (
            <button
              key={scenario.chip}
              disabled={busy}
              onClick={() => runTurn(scenario.preset)}
              style={{
                padding: "9px 16px",
                borderRadius: 999,
                border: "1px solid var(--border)",
                background: "var(--bg-raised)",
                color: "var(--text-muted)",
                fontSize: 12.5,
                fontWeight: 600,
                opacity: busy ? 0.5 : 1,
              }}
            >
              {scenario.chip}
            </button>
          ))}
        </div>
      </div>

      {/* Status strip */}
      {badges.length > 0 && (
        <div style={{ padding: "16px 32px 0 32px", display: "flex", flexWrap: "wrap", gap: 10 }}>
          {badges.map((badge) => (
            <div
              key={badge.label}
              className="badge"
              style={{ background: TINTS[badge.kind].bg, color: TINTS[badge.kind].fg }}
            >
              <StatusIcon kind={badge.kind} color={TINTS[badge.kind].fg} />
              {badge.label}
            </div>
          ))}
        </div>
      )}

      {/* Transcript */}
      <div style={{ flex: 1, display: "flex", justifyContent: "center", padding: "22px 32px 28px 32px" }}>
        <div style={{ width: "100%", maxWidth: 720, display: "flex", flexDirection: "column", gap: 4 }}>
          {entries.map((entry, index) => {
            if (entry.role === "merchant") {
              return (
                <div key={index} style={{ display: "flex", flexDirection: "column", alignItems: "flex-end", margin: "8px 0 2px 0" }}>
                  <div
                    style={{
                      maxWidth: "76%",
                      background: "var(--teal)",
                      color: "var(--teal-deep)",
                      padding: "11px 15px",
                      borderRadius: "16px 16px 3px 16px",
                      fontSize: 14,
                      lineHeight: 1.45,
                      fontWeight: 500,
                      boxShadow: "0 6px 16px rgba(45,212,191,0.12)",
                    }}
                  >
                    {entry.text}
                  </div>
                  <div style={{ display: "flex", alignItems: "center", gap: 4, marginTop: 4, paddingRight: 2 }}>
                    <span style={{ fontSize: 10.5, color: "var(--text-faint)" }}>{entry.time}</span>
                    <DoubleCheck />
                  </div>
                </div>
              );
            }
            if (entry.role === "progress") {
              const fg = entry.ok ? "#2dd4bf" : "#f5b351";
              const bg = entry.ok ? "rgba(45,212,191,0.18)" : "rgba(245,179,81,0.18)";
              return (
                <div key={index} style={{ display: "flex", alignItems: "center", gap: 8, padding: "5px 2px", fontSize: 12.5, color: "var(--text-muted)" }}>
                  <div
                    style={{
                      width: 17,
                      height: 17,
                      borderRadius: "50%",
                      background: bg,
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                      flexShrink: 0,
                    }}
                  >
                    <Check color={fg} />
                  </div>
                  {entry.text}
                </div>
              );
            }
            if (entry.role === "agent") {
              return (
                <div key={index} style={{ display: "flex", alignItems: "flex-end", gap: 8, margin: "6px 0 10px 0" }}>
                  <div
                    style={{
                      width: 26,
                      height: 26,
                      borderRadius: "50%",
                      background: "var(--teal)",
                      flexShrink: 0,
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                      fontWeight: 800,
                      color: "var(--teal-deep)",
                      fontSize: 12,
                    }}
                  >
                    P
                  </div>
                  <div>
                    <div
                      style={{
                        maxWidth: 460,
                        background: "var(--bg-card)",
                        border: "1px solid var(--border)",
                        padding: "12px 16px",
                        borderRadius: "16px 16px 16px 3px",
                        fontSize: 14,
                        lineHeight: 1.55,
                        boxShadow: "0 8px 20px rgba(0,0,0,0.18)",
                      }}
                    >
                      {entry.text}
                    </div>
                    <div style={{ fontSize: 10.5, color: "var(--text-faint)", marginTop: 4, marginLeft: 3 }}>{entry.time}</div>
                  </div>
                </div>
              );
            }
            return (
              <div key={index} className="badge" style={{ background: TINTS.err.bg, color: TINTS.err.fg, marginTop: 8 }}>
                {entry.text}
              </div>
            );
          })}

          {busy && (
            <div style={{ fontSize: 12.5, color: "var(--text-faint)", padding: "6px 2px" }}>
              {recording ? "Listening…" : "PayTrail is investigating…"}
            </div>
          )}
        </div>
      </div>

      {/* Composer */}
      <div style={{ padding: "14px 32px 26px 32px", display: "flex", justifyContent: "center" }}>
        <form
          onSubmit={(event) => {
            event.preventDefault();
            const message = input;
            setInput("");
            runTurn(message);
          }}
          style={{
            width: "100%",
            maxWidth: 720,
            display: "flex",
            alignItems: "center",
            gap: 8,
            background: "var(--bg-raised)",
            border: "1px solid var(--border)",
            borderRadius: 16,
            padding: "8px 8px 8px 18px",
            boxShadow: "0 10px 26px rgba(0,0,0,0.22)",
          }}
        >
          <input
            type="text"
            value={input}
            onChange={(event) => setInput(event.target.value)}
            placeholder="Type your issue, in any language…"
            aria-label="Message"
            style={{
              flex: 1,
              minWidth: 0,
              background: "transparent",
              border: "none",
              outline: "none",
              color: "var(--text)",
              fontSize: 14,
            }}
          />
          <button
            type="button"
            onClick={recording ? stopRecording : startRecording}
            aria-label={recording ? "Stop recording" : "Record voice message"}
            style={{
              width: 38,
              height: 38,
              borderRadius: 11,
              border: "1px solid var(--border)",
              background: recording ? "#f29a9a" : "transparent",
              color: recording ? "#3a1a1e" : "var(--text-muted)",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
            }}
          >
            {recording ? <Stop /> : <Mic />}
          </button>
          <button
            type="submit"
            aria-label="Send message"
            disabled={busy}
            style={{
              width: 38,
              height: 38,
              borderRadius: 11,
              border: "none",
              background: "var(--teal)",
              color: "var(--teal-deep)",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              boxShadow: "0 4px 14px rgba(45,212,191,0.3)",
              opacity: busy ? 0.6 : 1,
            }}
          >
            <Send />
          </button>
        </form>
      </div>
    </div>
  );
}
