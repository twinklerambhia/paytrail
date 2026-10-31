"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Layers, Search, StatusIcon, Users } from "@/components/Icons";
import { getCase, listCases, type CaseDetail, type CaseSummary } from "@/lib/api";

type Kind = "ok" | "warn" | "err";

const STATUS_KIND: Record<string, Kind> = {
  RESOLVED: "ok",
  CLOSED: "ok",
  ESCALATED: "err",
  OPEN: "warn",
  IN_PROGRESS: "warn",
  AWAITING_APPROVAL: "warn",
};

const TINTS: Record<Kind, { bg: string; fg: string }> = {
  ok: { bg: "var(--teal-tint-bg)", fg: "var(--teal-tint-text)" },
  warn: { bg: "var(--orange-tint-bg)", fg: "var(--orange-tint-text)" },
  err: { bg: "var(--red-tint-bg)", fg: "var(--red-tint-text)" },
};

const ICON_TINTS: Record<Kind, { bg: string; fg: string }> = {
  ok: { bg: "rgba(45,212,191,0.2)", fg: "#2dd4bf" },
  warn: { bg: "rgba(245,179,81,0.2)", fg: "#f5b351" },
  err: { bg: "rgba(242,154,154,0.2)", fg: "#f29a9a" },
};

function initials(name: string) {
  return name.replace(/[^A-Za-z0-9 ]/g, "").slice(0, 2).toUpperCase();
}

function shortTime(iso: string) {
  const date = new Date(iso);
  return Number.isNaN(date.getTime())
    ? iso
    : date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });
}

function relative(iso: string) {
  const then = new Date(iso).getTime();
  if (Number.isNaN(then)) return "";
  const minutes = Math.max(0, Math.round((Date.now() - then) / 60000));
  if (minutes < 1) return "just now";
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.round(minutes / 60);
  return hours < 24 ? `${hours}h ago` : `${Math.round(hours / 24)}d ago`;
}

function toolKind(ok: boolean, toolName: string, result: Record<string, any> | null): Kind {
  if (!ok) return "err";
  if (toolName === "verify_case_outcome" && result && result.issue_resolved === false) return "warn";
  if (toolName === "execute_device_action" && result) {
    // AWAITING_APPROVAL is a valid outcome, not an error (ok:true by design,
    // matching the brief's own example) — but nothing executed, so it must
    // never render identically to a completed action.
    if (result.execution_status === "AWAITING_APPROVAL") return "warn";
    const inner = result.result as Record<string, any> | null;
    if (inner && inner.device_reachable === false) return "warn";
  }
  return "ok";
}

function toolDetail(toolName: string, ok: boolean, result: Record<string, any> | null): string {
  const data = result ?? {};
  if (!ok) return (data.message as string) ?? (data.code as string) ?? "error";
  switch (toolName) {
    case "investigate_payment_case": {
      const txn = data.transaction ?? {};
      const device = data.device_summary;
      const bits = [`${txn.status ?? "?"} payment`];
      if (device) bits.push(device.online ? "device online" : "device offline");
      return bits.join(", ");
    }
    case "search_support_knowledge": {
      const results = data.results ?? [];
      return results.length > 0 ? results[0].title : "no matching guidance";
    }
    case "inspect_device":
      return `health: ${data.health_status ?? "?"}`;
    case "execute_device_action":
      if (data.execution_status === "AWAITING_APPROVAL") {
        return `awaiting human approval (${data.approval?.approval_request_id ?? "pending"}) — not executed`;
      }
      return JSON.stringify(data.result ?? {});
    case "verify_case_outcome":
      return `${data.verification_status ?? "?"} · ${data.issue_resolved ? "resolved" : "not resolved"}`;
    case "manage_support_case":
      return `status: ${data.status ?? "?"}${data.assigned_team ? `, team: ${data.assigned_team}` : ""}`;
    case "notify_merchant":
      return `${data.message_type ?? "?"} sent`;
    default:
      return "";
  }
}

export default function Dashboard() {
  const [cases, setCases] = useState<CaseSummary[]>([]);
  const [selected, setSelected] = useState<string | null>(null);
  const [detail, setDetail] = useState<CaseDetail | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    listCases()
      .then((rows) => {
        setCases(rows);
        if (rows.length > 0) setSelected((current) => current ?? rows[0].case_id);
      })
      .catch((err) => setError((err as Error).message));
  }, []);

  useEffect(() => {
    if (!selected) return;
    getCase(selected)
      .then(setDetail)
      .catch((err) => setError((err as Error).message));
  }, [selected]);

  if (error) {
    return (
      <div style={{ padding: 32 }}>
        <div className="badge" style={{ background: TINTS.err.bg, color: TINTS.err.fg }}>
          Couldn&apos;t reach PayTrail backend: {error}
        </div>
      </div>
    );
  }

  const caseRecord = detail?.case;
  const executions = detail?.tool_executions ?? [];
  const verification = detail?.verifications?.[0];
  const investigate = executions.find((t) => t.tool_name === "investigate_payment_case" && t.ok);

  // investigate_payment_case only captures device state at the moment of
  // investigation — a later execute_device_action/inspect_device call can
  // bring the device back online, but the Evidence card kept showing the
  // stale "offline" snapshot from the first call. Use whichever ran last.
  let latestDeviceOnline: boolean | undefined;
  for (const t of executions) {
    if (!t.ok || !t.result) continue;
    if (t.tool_name === "execute_device_action") {
      const inner = t.result.result as Record<string, any> | null;
      if (inner && "device_reachable" in inner) latestDeviceOnline = inner.device_reachable;
      else if (inner && "online" in inner) latestDeviceOnline = inner.online;
    } else if (t.tool_name === "inspect_device") {
      const connectivity = t.result.connectivity as Record<string, any> | undefined;
      if (connectivity && "online" in connectivity) latestDeviceOnline = connectivity.online;
    }
  }

  const caseKind: Kind = caseRecord ? STATUS_KIND[caseRecord.status] ?? "warn" : "warn";

  return (
    <div style={{ minHeight: "100vh", display: "flex", flexWrap: "wrap" }}>
      {/* Case list */}
      <div
        style={{
          width: 340,
          flex: "0 0 340px",
          borderRight: "1px solid var(--border)",
          padding: "20px 0",
          background: "#0d1e35",
        }}
      >
        <div style={{ padding: "0 18px 14px 18px", display: "flex", alignItems: "center", gap: 10 }}>
          <div className="brandMark" style={{ width: 28, height: 28, borderRadius: 8, fontSize: 13 }}>
            P
          </div>
          <div style={{ fontWeight: 800, fontSize: 14.5 }}>Support queue</div>
        </div>

        <div style={{ padding: "0 18px 14px 18px" }}>
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: 8,
              background: "var(--bg-raised)",
              border: "1px solid var(--border)",
              borderRadius: 10,
              padding: "8px 12px",
            }}
          >
            <Search color="var(--text-faint)" />
            <span style={{ fontSize: 12.5, color: "var(--text-faint)" }}>Search cases, merchants…</span>
          </div>
          <div style={{ display: "flex", gap: 6, marginTop: 10 }}>
            {["All", "Open", "Escalated", "Resolved"].map((filter, index) => (
              <span
                key={filter}
                style={{
                  fontSize: 11,
                  fontWeight: 700,
                  padding: "5px 10px",
                  borderRadius: 999,
                  border: "1px solid var(--border)",
                  background: index === 0 ? "var(--teal-tint-bg)" : "transparent",
                  color: index === 0 ? "var(--teal-tint-text)" : "var(--text-muted)",
                }}
              >
                {filter}
              </span>
            ))}
          </div>
          <Link href="/" className="navLink" style={{ display: "inline-block", marginTop: 12 }}>
            ← Merchant chat
          </Link>
        </div>

        {cases.length === 0 && (
          <div style={{ padding: "0 18px", fontSize: 12.5, color: "var(--text-faint)" }}>
            No cases yet — run the agent from the merchant chat first.
          </div>
        )}

        {cases.map((row) => {
          const active = row.case_id === selected;
          const kind = STATUS_KIND[row.status] ?? "warn";
          return (
            <button
              key={row.case_id}
              onClick={() => setSelected(row.case_id)}
              style={{
                width: "100%",
                textAlign: "left",
                border: "none",
                borderLeft: `3px solid ${active ? "var(--teal)" : "transparent"}`,
                background: active ? "var(--bg-raised)" : "transparent",
                color: "var(--text)",
                padding: "12px 18px",
              }}
            >
              <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                <div
                  style={{
                    width: 30,
                    height: 30,
                    borderRadius: "50%",
                    background: "#1e3a5c",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    fontSize: 11,
                    fontWeight: 700,
                    flexShrink: 0,
                  }}
                >
                  {initials(row.merchant_id)}
                </div>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 8 }}>
                    <span
                      style={{
                        fontWeight: 700,
                        fontSize: 13,
                        whiteSpace: "nowrap",
                        overflow: "hidden",
                        textOverflow: "ellipsis",
                      }}
                    >
                      {row.case_id}
                    </span>
                    <span
                      style={{
                        fontSize: 10,
                        fontWeight: 700,
                        padding: "3px 8px",
                        borderRadius: 6,
                        background: TINTS[kind].bg,
                        color: TINTS[kind].fg,
                        flexShrink: 0,
                      }}
                    >
                      {row.status}
                    </span>
                  </div>
                  <div style={{ display: "flex", justifyContent: "space-between", gap: 8, marginTop: 3 }}>
                    <span style={{ fontSize: 11.5, color: "var(--text-muted)" }}>{row.issue_type}</span>
                    <span style={{ fontSize: 10.5, color: "var(--text-faint)", flexShrink: 0 }}>
                      {relative(row.updated_at)}
                    </span>
                  </div>
                </div>
              </div>
            </button>
          );
        })}
      </div>

      {/* Detail */}
      <div style={{ flex: "999 1 760px", minWidth: 0, padding: "26px 36px" }}>
        {!caseRecord ? (
          <div style={{ fontSize: 13, color: "var(--text-muted)" }}>Select a case from the queue.</div>
        ) : (
          <>
            <div
              style={{
                display: "flex",
                flexWrap: "wrap",
                justifyContent: "space-between",
                alignItems: "flex-start",
                gap: 16,
                marginBottom: 22,
              }}
            >
              <div>
                <div
                  className="mono"
                  style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 11, color: "var(--text-faint)", marginBottom: 6 }}
                >
                  <span>{caseRecord.merchant_id}</span>
                  <span>·</span>
                  <span>ref {caseRecord.transaction_id ?? "—"}</span>
                </div>
                <div style={{ fontSize: 21, fontWeight: 800 }}>
                  {caseRecord.case_id} — {caseRecord.issue_type}
                </div>
              </div>
              <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
                <span className="badge" style={{ background: TINTS[caseKind].bg, color: TINTS[caseKind].fg }}>
                  <StatusIcon kind={caseKind} color={TINTS[caseKind].fg} />
                  {caseRecord.status}
                </span>
                <span
                  className="badge"
                  style={{ background: "var(--bg-raised)", border: "1px solid var(--border)", color: "var(--text-muted)" }}
                >
                  {caseRecord.priority} priority
                </span>
                {caseRecord.assigned_team && (
                  <span
                    className="badge"
                    style={{ background: "var(--bg-raised)", border: "1px solid var(--border)", color: "var(--text-muted)" }}
                  >
                    <Users />
                    {caseRecord.assigned_team}
                  </span>
                )}
              </div>
            </div>

            <div style={{ display: "grid", gridTemplateColumns: "repeat(2, minmax(0, 1fr))", gap: 20 }}>
              {/* Timeline */}
              <div className="card" style={{ gridColumn: "1 / -1" }}>
                <div className="cardLabel">Investigation timeline</div>
                {executions.length === 0 && (
                  <div style={{ fontSize: 12.5, color: "var(--text-muted)" }}>No tool calls recorded yet.</div>
                )}
                {executions.map((step, index) => {
                  const kind = toolKind(step.ok, step.tool_name, step.result);
                  const isLast = index === executions.length - 1;
                  return (
                    <div key={`${step.tool_name}-${index}`} style={{ display: "flex", gap: 14 }}>
                      <div style={{ display: "flex", flexDirection: "column", alignItems: "center" }}>
                        <div
                          style={{
                            width: 22,
                            height: 22,
                            borderRadius: "50%",
                            background: ICON_TINTS[kind].bg,
                            display: "flex",
                            alignItems: "center",
                            justifyContent: "center",
                            flexShrink: 0,
                          }}
                        >
                          <StatusIcon kind={kind} size={12} color={ICON_TINTS[kind].fg} />
                        </div>
                        {!isLast && <div style={{ width: 1, flex: 1, background: "var(--border)", margin: "2px 0" }} />}
                      </div>
                      <div style={{ flex: 1, paddingBottom: 16 }}>
                        <div
                          style={{
                            display: "flex",
                            justifyContent: "space-between",
                            gap: 8,
                            flexWrap: "wrap",
                            alignItems: "baseline",
                          }}
                        >
                          <span className="mono" style={{ fontSize: 13, fontWeight: 700 }}>
                            {step.tool_name}
                          </span>
                          <span className="mono" style={{ fontSize: 10.5, color: "var(--text-faint)" }}>
                            {shortTime(step.created_at)}
                          </span>
                        </div>
                        <div style={{ fontSize: 12.5, color: "var(--text-muted)", marginTop: 3 }}>
                          {toolDetail(step.tool_name, step.ok, step.result)}
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>

              {/* Evidence */}
              <div className="card">
                <div className="cardLabel">Evidence</div>
                {!investigate && (
                  <div style={{ fontSize: 12.5, color: "var(--text-muted)" }}>No investigation evidence yet.</div>
                )}
                {investigate &&
                  (() => {
                    const data = investigate.result ?? {};
                    const txn = (data.transaction ?? {}) as Record<string, any>;
                    const device = data.device_summary as Record<string, any> | null;
                    const rows: { label: string; value: string }[] = [];
                    if (txn.status) {
                      rows.push({
                        label: "Payment status",
                        value:
                          txn.amount !== undefined
                            ? `${txn.status} · ₹${Number(txn.amount).toLocaleString("en-IN", { minimumFractionDigits: 2 })}`
                            : txn.status,
                      });
                    }
                    const deviceOnline = latestDeviceOnline !== undefined ? latestDeviceOnline : device?.online;
                    if (deviceOnline !== undefined) rows.push({ label: "Device", value: deviceOnline ? "online" : "offline" });
                    return rows.map((row) => (
                      <div
                        key={row.label}
                        style={{
                          display: "flex",
                          justifyContent: "space-between",
                          gap: 10,
                          fontSize: 12.5,
                          borderBottom: "1px solid var(--border)",
                          paddingBottom: 8,
                          marginBottom: 9,
                        }}
                      >
                        <span style={{ color: "var(--text-muted)" }}>{row.label}</span>
                        <span className="mono" style={{ fontWeight: 600, textAlign: "right", fontSize: 12 }}>
                          {row.value}
                        </span>
                      </div>
                    ));
                  })()}
              </div>

              {/* Verification */}
              <div className="card">
                <div className="cardLabel">Verification result</div>
                {!verification ? (
                  <div style={{ fontSize: 12.5, color: "var(--text-muted)" }}>Not yet verified.</div>
                ) : (
                  (() => {
                    const vKind: Kind =
                      verification.status === "VERIFIED" ? "ok" : verification.status === "FAILED" ? "err" : "warn";
                    return (
                      <>
                        <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 10 }}>
                          <span className="badge" style={{ background: TINTS[vKind].bg, color: TINTS[vKind].fg }}>
                            <StatusIcon kind={vKind} color={TINTS[vKind].fg} />
                            {verification.status}
                          </span>
                          <span className="mono" style={{ fontSize: 11.5, color: "var(--text-faint)" }}>
                            {verification.verification_scope}
                          </span>
                        </div>
                        <div style={{ fontSize: 12.5, color: "var(--text-muted)", lineHeight: 1.55 }}>
                          {verification.mismatches.length > 0
                            ? verification.mismatches.join(" · ")
                            : "No mismatches — resolution supported."}
                        </div>
                      </>
                    );
                  })()
                )}
              </div>

              {/* Outcome */}
              <div
                style={{
                  gridColumn: "1 / -1",
                  background: "var(--bg-raised)",
                  border: "1px solid var(--border)",
                  borderRadius: 14,
                  padding: "16px 22px",
                  display: "flex",
                  flexWrap: "wrap",
                  justifyContent: "space-between",
                  alignItems: "center",
                  gap: 12,
                }}
              >
                <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                  <div
                    style={{
                      width: 30,
                      height: 30,
                      borderRadius: 9,
                      background: ICON_TINTS[caseKind].bg,
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                      flexShrink: 0,
                    }}
                  >
                    <Layers color={ICON_TINTS[caseKind].fg} />
                  </div>
                  <div>
                    <div
                      style={{
                        fontSize: 11,
                        fontWeight: 700,
                        color: "var(--text-faint)",
                        textTransform: "uppercase",
                        letterSpacing: 0.6,
                      }}
                    >
                      Outcome
                    </div>
                    <div style={{ fontSize: 13.5, fontWeight: 700, marginTop: 2 }}>
                      {caseRecord.status === "ESCALATED"
                        ? `Escalated to ${caseRecord.assigned_team ?? "a human team"}`
                        : caseRecord.status.replace(/_/g, " ")}
                    </div>
                  </div>
                </div>
                <div style={{ fontSize: 12.5, color: "var(--text-muted)", maxWidth: 420 }}>
                  {caseRecord.summary ?? "No summary yet."}
                </div>
              </div>
            </div>

            {detail!.notes.length > 0 && (
              <div style={{ marginTop: 18 }}>
                {detail!.notes.map((note, index) => (
                  <div key={index} style={{ fontSize: 12, color: "var(--text-faint)", marginBottom: 6 }}>
                    {shortTime(note.created_at)}: {note.note}
                  </div>
                ))}
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}
