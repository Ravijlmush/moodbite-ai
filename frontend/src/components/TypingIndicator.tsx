"use client";

import React from "react";

interface TypingIndicatorProps {
  statusText: string;
}

export function TypingIndicator({ statusText }: TypingIndicatorProps) {
  return (
    <div className="flex flex-col items-start gap-1.5">
      <span
        className="font-mono-meta text-[11px] font-semibold uppercase tracking-[0.08em]"
        style={{ color: "var(--text-secondary)" }}
      >
        MOODBITE
      </span>
      <div
        className="flex items-center gap-3 px-4 py-3"
        style={{
          backgroundColor: "var(--bg-primary)",
          border: "1px solid var(--border-color)",
          borderRadius: "12px 12px 12px 2px",
        }}
      >
        <span className="flex items-center gap-1.5" aria-hidden="true">
          <span className="bw-dot" />
          <span className="bw-dot" />
          <span className="bw-dot" />
        </span>
        <span
          className="font-mono-meta text-[12px]"
          style={{ color: "var(--text-secondary)" }}
        >
          {statusText || "Reading the vibe..."}
        </span>
      </div>
    </div>
  );
}
