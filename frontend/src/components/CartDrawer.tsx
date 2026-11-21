"use client";

import React, { useState } from "react";
import { CartResponse } from "@/lib/types";

interface CartDrawerProps {
  open: boolean;
  cart: CartResponse;
  onClose: () => void;
  onRemoveItem: (comboId: string) => void;
}

export function CartDrawer({
  open,
  cart,
  onClose,
  onRemoveItem,
}: CartDrawerProps) {
  const [checkedOut, setCheckedOut] = useState(false);

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
              YOUR MOODBITE CART
            </h2>
            <p
              className="font-mono-meta text-[11px]"
              style={{ color: "var(--text-secondary)" }}
            >
              {cart.total_items} COMBO{cart.total_items === 1 ? "" : "S"} • TOTAL ₹{cart.total_price_inr}
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
          {cart.items.length === 0 ? (
            <div
              className="p-5 text-center"
              style={{
                border: "var(--border-hairline)",
                borderRadius: "12px",
                backgroundColor: "var(--bg-subtle)",
              }}
            >
              <p className="text-[14px]" style={{ color: "var(--text-secondary)" }}>
                Your cart is empty. Tap + ADD COMBO TO CART on any recommendation.
              </p>
            </div>
          ) : (
            cart.items.map((entry) => (
              <div
                key={entry.combo.combo_id}
                className="p-3.5"
                style={{
                  border: "1px solid var(--border-color)",
                  borderRadius: "10px",
                  backgroundColor: "var(--bg-primary)",
                }}
              >
                <div className="flex items-start justify-between gap-2">
                  <div>
                    <p
                      className="text-[14px] font-bold"
                      style={{ color: "var(--text-primary)" }}
                    >
                      {entry.combo.title}
                    </p>
                    <p
                      className="font-mono-meta mt-0.5 text-[11px]"
                      style={{ color: "var(--text-secondary)" }}
                    >
                      {entry.combo.restaurant.name} • {entry.combo.restaurant.eta_mins} MINS • QTY {entry.quantity}
                    </p>
                  </div>
                  <span
                    className="font-mono-meta text-[13px] font-bold"
                    style={{ color: "var(--text-primary)" }}
                  >
                    ₹{entry.line_total_inr}
                  </span>
                </div>
                <button
                  type="button"
                  onClick={() => {
                    setCheckedOut(false);
                    onRemoveItem(entry.combo.combo_id);
                  }}
                  className="font-mono-meta mt-2.5 cursor-pointer px-2.5 py-1 text-[11px] font-semibold uppercase"
                  style={{
                    border: "1px solid var(--border-color)",
                    borderRadius: "6px",
                    color: "var(--text-primary)",
                  }}
                >
                  REMOVE
                </button>
              </div>
            ))
          )}
        </div>

        {cart.items.length > 0 ? (
          <div className="pt-3" style={{ borderTop: "var(--border-strong)" }}>
            <div className="mb-3 flex items-center justify-between">
              <span
                className="font-mono-meta text-[12px] font-semibold uppercase"
                style={{ color: "var(--text-secondary)" }}
              >
                ORDER TOTAL
              </span>
              <span
                className="font-mono-meta text-[18px] font-bold"
                style={{ color: "var(--text-primary)" }}
              >
                ₹{cart.total_price_inr}
              </span>
            </div>
            <button
              type="button"
              onClick={() => setCheckedOut(true)}
              className="font-mono-meta w-full cursor-pointer py-3 text-[12px] font-semibold uppercase tracking-wider"
              style={{
                border: "var(--border-strong)",
                borderRadius: "8px",
                backgroundColor: checkedOut ? "var(--bg-primary)" : "var(--bg-inverse)",
                color: checkedOut ? "var(--text-primary)" : "var(--text-inverse)",
              }}
            >
              {checkedOut
                ? "✓ ORDER PLACED (DEMO CONFIRMATION)"
                : `PLACE ORDER • ₹${cart.total_price_inr}`}
            </button>
          </div>
        ) : null}
      </aside>
    </div>
  );
}
