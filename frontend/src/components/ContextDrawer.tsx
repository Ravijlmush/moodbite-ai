"use client";

import React from "react";
import { FullUserContext, HealthResponse } from "@/lib/types";

interface ContextDrawerProps {
  open: boolean;
  context: FullUserContext | null;
  health: HealthResponse | null;
  lastLatencyMs: number | null;
  llmMode: string;
  onClose: () => void;
}

export function ContextDrawer({
  open,
  context,
  health,
  lastLatencyMs,
  llmMode,
  onClose,
}: ContextDrawerProps) {
  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-40 flex justify-end"
      style={{ backgroundColor: "rgba(0, 0, 0, 0.45)" }}
      onClick={onClose}
    >
      <aside
        className="flex h-full w-full max-w-md flex-col p-5"
        style={{
          backgroundColor: "var(--bg-primary)",
          borderLeft: "var(--border-strong)",
        }}
        onClick={(e) => e.stopPropagation()}
      >
        <div
          className="flex items-center justify-between pb-3"
          style={{ borderBottom: "var(--border-strong)" }}
        >
          <div>
            <h2
              className="text-[16px] font-bold uppercase tracking-wide"
              style={{ color: "var(--text-primary)" }}
            >
              LIVE USERCONTEXT &amp; ENGINE
            </h2>
            <p
              className="font-mono-meta text-[11px]"
              style={{ color: "var(--text-secondary)" }}
            >
              MODE: {llmMode.toUpperCase()}
              {lastLatencyMs !== null ? ` • ${lastLatencyMs.toFixed(1)} MS` : ""}
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="font-mono-meta cursor-pointer px-2.5 py-1 text-[12px] font-semibold"
            style={{
              border: "1px solid var(--border-color)",
              borderRadius: "6px",
              color: "var(--text-primary)",
            }}
          >
            CLOSE
          </button>
        </div>

        <div className="my-4 flex-1 space-y-3 overflow-y-auto">
          <div
            className="p-3.5"
            style={{
              border: "1px solid var(--border-color)",
              borderRadius: "10px",
              backgroundColor: "var(--bg-subtle)",
            }}
          >
            <p
              className="font-mono-meta text-[11px] font-semibold uppercase"
              style={{ color: "var(--text-primary)" }}
            >
              RUNTIME STATUS
            </p>
            <div
              className="font-mono-meta mt-2 space-y-1 text-[12px]"
              style={{ color: "var(--text-secondary)" }}
            >
              <p>LLM PROVIDER: {health?.llm_provider?.toUpperCase() || llmMode.toUpperCase()}</p>
              <p>CATALOG ITEMS: {health?.catalog_items ?? "—"} ({health?.catalog_restaurants ?? "—"} RESTAURANTS)</p>
              <p>STORAGE: {health?.storage_backend || "in_memory_ttl"}</p>
              <p>
                DAILY QUOTA: {health ? `${health.daily_requests_used} / ${health.daily_request_limit} USED` : "0 / 20 USED"}
              </p>
              <p>TURN COUNTER: {context?.turn_count ?? 0} / 3 MAX</p>
            </div>
            <p
              className="mt-2.5 text-[12px]"
              style={{ color: "var(--text-secondary)" }}
            >
              API key optional: running offline deterministic extractor now. Add{" "}
              <code className="font-mono-meta">OPENROUTER_API_KEY</code> (or{" "}
              <code className="font-mono-meta">OPENAI_API_KEY</code> /{" "}
              <code className="font-mono-meta">GEMINI_API_KEY</code>) to{" "}
              <code className="font-mono-meta">backend/.env</code> anytime to activate live LLM extraction.
            </p>
          </div>

          <div
            className="p-3.5"
            style={{
              border: "1px solid var(--border-color)",
              borderRadius: "10px",
              backgroundColor: "var(--bg-primary)",
            }}
          >
            <p
              className="font-mono-meta mb-2 text-[11px] font-semibold uppercase"
              style={{ color: "var(--text-primary)" }}
            >
              EXTRACTED USERCONTEXT JSON
            </p>
            <pre
              className="font-mono-meta overflow-x-auto text-[11px] leading-relaxed"
              style={{ color: "var(--text-primary)" }}
            >
              {context
                ? JSON.stringify(context, null, 2)
                : "{\n  \"status\": \"Waiting for Turn 1 message\"\n}"}
            </pre>
          </div>
        </div>
      </aside>
    </div>
  );
}
