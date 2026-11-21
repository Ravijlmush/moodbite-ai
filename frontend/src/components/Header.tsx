"use client";

import Link from "next/link";
import React from "react";

interface HeaderProps {
  vegOnly: boolean;
  onToggleVegOnly: () => void;
  cartCount: number;
  onOpenCart: () => void;
  onOpenContext: () => void;
  onOpenSwiggy: () => void;
  swiggyConnected: boolean;
  showStatePill: boolean;
  onToggleStatePill: () => void;
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
  onOpenSwiggy,
  swiggyConnected,
  showStatePill,
  onToggleStatePill,
  darkMode,
  onToggleTheme,
  onResetSession,
}: HeaderProps) {
  return (
    <header
      className="sticky top-0 z-20 flex items-center justify-between gap-2 px-3.5 py-3"
      style={{
        backgroundColor: "var(--bg-primary)",
        borderBottom: "var(--border-strong)",
      }}
    >
      <div className="flex items-center gap-2">
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
            className="text-[15px] font-semibold tracking-[-0.02em]"
            style={{ color: "var(--text-primary)" }}
          >
            MOODBITE × SWIGGY MCP
          </h1>
        </div>
      </div>

      <div className="flex flex-wrap items-center justify-end gap-1">
        <button
          type="button"
          onClick={onToggleVegOnly}
          aria-pressed={vegOnly}
          className="font-mono-meta cursor-pointer px-2 py-1.5 text-[10px] font-semibold uppercase tracking-wide"
          style={{
            borderRadius: "6px",
            border: "1px solid var(--border-color)",
            backgroundColor: vegOnly ? "var(--bg-inverse)" : "var(--bg-primary)",
            color: vegOnly ? "var(--text-inverse)" : "var(--text-primary)",
          }}
        >
          {vegOnly ? "VEG ✓" : "VEG"}
        </button>

        <button
          type="button"
          onClick={onOpenSwiggy}
          title="Swiggy Food MCP OAuth & Addresses"
          className="font-mono-meta cursor-pointer px-2 py-1.5 text-[10px] font-semibold uppercase tracking-wide"
          style={{
            borderRadius: "6px",
            border: "1px solid var(--border-color)",
            backgroundColor: swiggyConnected ? "var(--bg-inverse)" : "var(--bg-primary)",
            color: swiggyConnected ? "var(--text-inverse)" : "var(--text-primary)",
          }}
        >
          {swiggyConnected ? "MCP LIVE" : "MCP"}
        </button>

        <button
          type="button"
          onClick={onToggleStatePill}
          onDoubleClick={onOpenContext}
          title="Toggle live State Inspector pills (double-click for full JSON drawer)"
          className="font-mono-meta cursor-pointer px-2 py-1.5 text-[10px] font-semibold uppercase tracking-wide"
          style={{
            borderRadius: "6px",
            border: "1px solid var(--border-color)",
            backgroundColor: showStatePill ? "var(--bg-inverse)" : "var(--bg-primary)",
            color: showStatePill ? "var(--text-inverse)" : "var(--text-primary)",
          }}
        >
          STATE
        </button>

        <button
          type="button"
          onClick={onOpenContext}
          title="Open full UserContext JSON drawer"
          className="font-mono-meta cursor-pointer px-2 py-1.5 text-[10px] font-semibold uppercase tracking-wide"
          style={{
            borderRadius: "6px",
            border: "1px solid var(--border-color)",
            backgroundColor: "var(--bg-primary)",
            color: "var(--text-primary)",
          }}
        >
          CTX
        </button>

        <Link
          href="/tests"
          title="View 30-Prompt Safety, Injection & Load Stress Suite Report"
          className="font-mono-meta inline-flex items-center px-2 py-1.5 text-[10px] font-semibold uppercase tracking-wide"
          style={{
            borderRadius: "6px",
            border: "1px solid var(--border-color)",
            backgroundColor: "var(--bg-primary)",
            color: "var(--text-primary)",
          }}
        >
          TESTS
        </Link>

        <button
          type="button"
          onClick={onOpenCart}
          className="font-mono-meta cursor-pointer px-2 py-1.5 text-[10px] font-semibold uppercase tracking-wide"
          style={{
            borderRadius: "6px",
            border: "1px solid var(--border-color)",
            backgroundColor: cartCount > 0 ? "var(--bg-inverse)" : "var(--bg-primary)",
            color: cartCount > 0 ? "var(--text-inverse)" : "var(--text-primary)",
          }}
        >
          CART: {cartCount}
        </button>

        <button
          type="button"
          onClick={onToggleTheme}
          title={darkMode ? "Switch to Light Monochrome" : "Switch to Dark Monochrome"}
          aria-label="Toggle monochrome theme"
          className="font-mono-meta flex h-7 w-7 cursor-pointer items-center justify-center text-[11px] font-semibold"
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
