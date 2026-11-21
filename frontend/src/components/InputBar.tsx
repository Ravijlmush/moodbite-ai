"use client";

import React, { FormEvent, useState } from "react";

interface InputBarProps {
  disabled?: boolean;
  onSend: (message: string) => void;
}

export function InputBar({ disabled = false, onSend }: InputBarProps) {
  const [text, setText] = useState("");

  function handleSubmit(e: FormEvent) {
    e.preventDefault();
    const trimmed = text.trim();
    if (!trimmed || disabled) return;
    onSend(trimmed);
    setText("");
  }

  return (
    <form
      onSubmit={handleSubmit}
      className="sticky bottom-0 z-20 px-4 py-3"
      style={{
        backgroundColor: "var(--bg-primary)",
        borderTop: "var(--border-strong)",
      }}
    >
      <div
        className="flex items-center gap-2 px-3 py-1.5"
        style={{
          backgroundColor: "var(--bg-primary)",
          border: "var(--border-strong)",
          borderRadius: "var(--radius-input)",
        }}
      >
        <input
          type="text"
          value={text}
          disabled={disabled}
          onChange={(e) => setText(e.target.value)}
          placeholder="Type how you're feeling..."
          aria-label="Type how you're feeling"
          className="w-full bg-transparent py-1.5 text-[15px] outline-none placeholder:opacity-70"
          style={{ color: "var(--text-primary)" }}
        />
        <button
          type="submit"
          disabled={disabled || !text.trim()}
          aria-label="Send message"
          className="font-mono-meta shrink-0 cursor-pointer px-3 py-1.5 text-[12px] font-semibold uppercase transition-opacity disabled:cursor-not-allowed disabled:opacity-35"
          style={{
            backgroundColor: "var(--bg-inverse)",
            color: "var(--text-inverse)",
            borderRadius: "6px",
          }}
        >
          -&gt;
        </button>
      </div>
    </form>
  );
}
