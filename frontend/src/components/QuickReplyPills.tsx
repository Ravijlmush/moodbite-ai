"use client";

import React from "react";

interface QuickReplyPillsProps {
  pills: string[];
  label?: string;
  disabled?: boolean;
  onSelect: (pill: string) => void;
}

export function QuickReplyPills({
  pills,
  label,
  disabled = false,
  onSelect,
}: QuickReplyPillsProps) {
  if (!pills || pills.length === 0) return null;

  return (
    <div className="mt-2.5 flex flex-col gap-2">
      {label ? (
        <span
          className="font-mono-meta text-[11px] font-semibold uppercase tracking-[0.08em]"
          style={{ color: "var(--text-secondary)" }}
        >
          {label}
        </span>
      ) : null}
      <div className="flex flex-wrap gap-2">
        {pills.map((pill) => (
          <button
            key={pill}
            type="button"
            disabled={disabled}
            onClick={() => onSelect(pill)}
            className="pill-btn cursor-pointer px-3.5 py-1.5 text-[13px] font-medium disabled:cursor-not-allowed disabled:opacity-40"
          >
            {pill}
          </button>
        ))}
      </div>
    </div>
  );
}
