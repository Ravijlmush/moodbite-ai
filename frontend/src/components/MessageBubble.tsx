"use client";

import React from "react";

interface MessageBubbleProps {
  role: "user" | "assistant";
  content: string;
}

export function MessageBubble({ role, content }: MessageBubbleProps) {
  if (role === "user") {
    return (
      <div className="flex justify-end">
        <div
          className="max-w-[82%] px-4 py-2.5 text-[15px] leading-[1.45]"
          style={{
            backgroundColor: "var(--bg-inverse)",
            color: "var(--text-inverse)",
            borderRadius: "12px 12px 2px 12px",
          }}
        >
          {content}
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col items-start gap-1.5">
      <span
        className="font-mono-meta text-[11px] font-semibold uppercase tracking-[0.08em]"
        style={{ color: "var(--text-secondary)" }}
      >
        MOODBITE
      </span>
      <div
        className="max-w-[92%] px-4 py-3 text-[15px] leading-[1.45]"
        style={{
          backgroundColor: "var(--bg-primary)",
          color: "var(--text-primary)",
          border: "1px solid var(--border-color)",
          borderRadius: "12px 12px 12px 2px",
        }}
      >
        {content}
      </div>
    </div>
  );
}
