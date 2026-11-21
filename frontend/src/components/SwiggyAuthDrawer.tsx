"use client";

import React, { FormEvent, useState } from "react";
import { getSwiggyOAuthLoginUrl } from "@/lib/api";
import { SwiggyAuthStatus } from "@/lib/types";

interface SwiggyAuthDrawerProps {
  open: boolean;
  status: SwiggyAuthStatus | null;
  selectedAddressId: string | null;
  onSelectAddress: (addressId: string) => void;
  onConnectToken: (token: string) => Promise<void>;
  onDisconnect: () => Promise<void>;
  onClose: () => void;
}

export function SwiggyAuthDrawer({
  open,
  status,
  selectedAddressId,
  onSelectAddress,
  onConnectToken,
  onDisconnect,
  onClose,
}: SwiggyAuthDrawerProps) {
  const [tokenInput, setTokenInput] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  if (!open) return null;

  const connected = Boolean(status?.connected);

  async function handleTokenSubmit(e: FormEvent) {
    e.preventDefault();
    const trimmed = tokenInput.trim();
    if (!trimmed || submitting) return;
    setSubmitting(true);
    setErrorMsg(null);
    try {
      await onConnectToken(trimmed);
      setTokenInput("");
    } catch (err) {
      setErrorMsg(err instanceof Error ? err.message : "Failed to connect Swiggy MCP token.");
    } finally {
      setSubmitting(false);
    }
  }

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
              SWIGGY FOOD MCP
            </h2>
            <p
              className="font-mono-meta text-[11px]"
              style={{ color: "var(--text-secondary)" }}
            >
              STATUS: {connected ? "LIVE CONNECTED" : "DEMO FALLBACK ACTIVE"}
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

        <div className="my-4 flex-1 space-y-4 overflow-y-auto">
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
              MCP ENDPOINT &amp; OAUTH 2.1 (PKCE)
            </p>
            <p
              className="font-mono-meta mt-1.5 text-[12px]"
              style={{ color: "var(--text-secondary)" }}
            >
              {status?.mcp_url || "https://mcp.swiggy.com/food"}
            </p>
            <p
              className="mt-2 text-[12px] leading-relaxed"
              style={{ color: "var(--text-secondary)" }}
            >
              Connect your Swiggy account via OAuth 2.1 + PKCE to fetch live delivery addresses,
              menus, coupons, and sync combos directly via <code className="font-mono-meta">update_food_cart</code>.
            </p>
            <div className="mt-3 flex flex-wrap gap-2">
              <a
                href={getSwiggyOAuthLoginUrl()}
                className="font-mono-meta inline-block px-3 py-2 text-[11px] font-semibold uppercase tracking-wide"
                style={{
                  backgroundColor: "var(--bg-inverse)",
                  color: "var(--text-inverse)",
                  borderRadius: "6px",
                  border: "var(--border-strong)",
                }}
              >
                {connected ? "RE-AUTH SWIGGY OAUTH 2.1" : "CONNECT VIA SWIGGY OAUTH 2.1"}
              </a>
              {connected ? (
                <button
                  type="button"
                  onClick={() => void onDisconnect()}
                  className="font-mono-meta cursor-pointer px-3 py-2 text-[11px] font-semibold uppercase"
                  style={{
                    backgroundColor: "var(--bg-primary)",
                    color: "var(--text-primary)",
                    borderRadius: "6px",
                    border: "1px solid var(--border-color)",
                  }}
                >
                  DISCONNECT
                </button>
              ) : null}
            </div>
          </div>

          <form
            onSubmit={handleTokenSubmit}
            className="p-3.5"
            style={{
              border: "1px solid var(--border-color)",
              borderRadius: "10px",
              backgroundColor: "var(--bg-primary)",
            }}
          >
            <p
              className="font-mono-meta text-[11px] font-semibold uppercase"
              style={{ color: "var(--text-primary)" }}
            >
              OR PASTE SWIGGY MCP BEARER TOKEN
            </p>
            <input
              type="password"
              value={tokenInput}
              onChange={(e) => setTokenInput(e.target.value)}
              placeholder="Paste OAuth access token..."
              className="font-mono-meta mt-2 w-full px-3 py-2 text-[12px] outline-none"
              style={{
                border: "1px solid var(--border-color)",
                borderRadius: "6px",
                backgroundColor: "var(--bg-primary)",
                color: "var(--text-primary)",
              }}
            />
            {errorMsg ? (
              <p className="mt-2 text-[12px]" style={{ color: "var(--text-primary)" }}>
                {errorMsg}
              </p>
            ) : null}
            <button
              type="submit"
              disabled={submitting || !tokenInput.trim()}
              className="font-mono-meta mt-2.5 w-full cursor-pointer py-2 text-[11px] font-semibold uppercase disabled:opacity-40"
              style={{
                backgroundColor: "var(--bg-inverse)",
                color: "var(--text-inverse)",
                borderRadius: "6px",
              }}
            >
              {submitting ? "CONNECTING..." : "ACTIVATE TOKEN"}
            </button>
          </form>

          {status?.addresses && status.addresses.length > 0 ? (
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
                SAVED SWIGGY ADDRESSES (get_addresses)
              </p>
              <div className="space-y-2">
                {status.addresses.map((addr) => {
                  const active = addr.address_id === selectedAddressId;
                  return (
                    <button
                      key={addr.address_id}
                      type="button"
                      onClick={() => onSelectAddress(addr.address_id)}
                      className="w-full cursor-pointer p-2.5 text-left"
                      style={{
                        borderRadius: "8px",
                        border: "1px solid var(--border-color)",
                        backgroundColor: active ? "var(--bg-inverse)" : "var(--bg-primary)",
                        color: active ? "var(--text-inverse)" : "var(--text-primary)",
                      }}
                    >
                      <p className="font-mono-meta text-[11px] font-semibold uppercase">
                        {addr.label} {active ? "✓" : ""}
                      </p>
                      <p className="mt-0.5 text-[12px] opacity-85">{addr.address_line}</p>
                    </button>
                  );
                })}
              </div>
            </div>
          ) : null}
        </div>
      </aside>
    </div>
  );
}
