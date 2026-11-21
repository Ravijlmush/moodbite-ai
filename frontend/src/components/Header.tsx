"use client";

import React from "react";

interface HeaderProps {
  vegOnly: boolean;
  onToggleVegOnly: () => void;
  cartCount: number;
  onOpenCart: () => void;
  onOpenContext: () => void;
  darkMode: boolean;
  onToggleTheme: () => void;
  onResetSession: () => void;
}

export function Header({
  vegOnly,
  onToggleVegOnly,
  cartCount,
  onOpenCart,
  onOpenContext,
  darkMode,
  onToggleTheme,
  onResetSession,
}: HeaderProps) {
  return (
    <header
      className="sticky top-0 z-20 flex items-center justify-between px-4 py-3"
      style={{
        backgroundColor: "var(--bg-primary)",
        borderBottom: "var(--border-strong)",
      }}
    >
      <div className="flex items-center gap-2.5">
        <button
          type="button"
          onClick={onResetSession}
          title="Start fresh conversation"
          aria-label="Reset conversation"
          className="font-mono-meta flex h-8 w-8 cursor-pointer items-center justify-center rounded-[8px] text-xs font-semibold transition-colors"
          style={{
            border: "1px solid var(--border-color)",
            backgroundColor: "var(--bg-primary)",
            color: "var(--text-primary)",
          }}
        >
          &lt;-
        </button>
        <div>
          <h1
            className="text-[18px] font-semibold tracking-[-0.02em]"
            style={{ color: "var(--text-primary)" }}
          >
            MOODBITE AI
          </h1>
        </div>
      </div>

      <div className="flex items-center gap-1.5">
        <button
          type="button"
          onClick={onToggleVegOnly}
          aria-pressed={vegOnly}
          className="font-mono-meta cursor-pointer px-2.5 py-1.5 text-[11px] font-semibold uppercase tracking-wide"
          style={{
            borderRadius: "6px",
            border: "1px solid var(--border-color)",
            backgroundColor: vegOnly ? "var(--bg-inverse)" : "var(--bg-primary)",
            color: vegOnly ? "var(--text-inverse)" : "var(--text-primary)",
          }}
        >
          {vegOnly ? "VEG ONLY ✓" : "VEG ONLY"}
        </button>

        <button
          type="button"
          onClick={onOpenContext}
          title="Inspect live UserContext & LLM mode"
          className="font-mono-meta cursor-pointer px-2.5 py-1.5 text-[11px] font-semibold uppercase tracking-wide"
          style={{
            borderRadius: "6px",
            border: "1px solid var(--border-color)",
            backgroundColor: "var(--bg-primary)",
            color: "var(--text-primary)",
          }}
        >
          CTX
        </button>

        <button
          type="button"
          onClick={onOpenCart}
          className="font-mono-meta cursor-pointer px-2.5 py-1.5 text-[11px] font-semibold uppercase tracking-wide"
          style={{
            borderRadius: "6px",
            border: "1px solid var(--border-color)",
            backgroundColor: cartCount > 0 ? "var(--bg-inverse)" : "var(--bg-primary)",
            color: cartCount > 0 ? "var(--text-inverse)" : "var(--text-primary)",
          }}
        >
          CART ({cartCount})
        </button>

        <button
          type="button"
          onClick={onToggleTheme}
          title={darkMode ? "Switch to Light Monochrome" : "Switch to Dark Monochrome"}
          aria-label="Toggle monochrome theme"
          className="font-mono-meta flex h-8 w-8 cursor-pointer items-center justify-center text-[11px] font-semibold"
          style={{
            borderRadius: "6px",
            border: "1px solid var(--border-color)",
            backgroundColor: "var(--bg-primary)",
            color: "var(--text-primary)",
          }}
        >
          {darkMode ? "●" : "○"}
        </button>
      </div>
    </header>
  );
}
