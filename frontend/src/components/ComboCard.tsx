"use client";

import React from "react";
import { ComboRecommendation } from "@/lib/types";

interface ComboCardProps {
  combo: ComboRecommendation;
  inCartQuantity: number;
  adding: boolean;
  onAddToCart: (combo: ComboRecommendation) => void;
}

function formatDietaryLabel(dietary: "veg" | "egg" | "non_veg"): string {
  if (dietary === "veg") return "VEG";
  if (dietary === "egg") return "EGG";
  return "NON-VEG";
}

export function ComboCard({
  combo,
  inCartQuantity,
  adding,
  onAddToCart,
}: ComboCardProps) {
  const added = inCartQuantity > 0;

  return (
    <article
      className="p-4"
      style={{
        backgroundColor: "var(--bg-primary)",
        border: "var(--border-strong)",
        borderRadius: "var(--radius-card)",
      }}
    >
      {/* Top Meta Row: Inverted Mood Badge + Dietary Tag | ETA & Price */}
      <div className="mb-2.5 flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-1.5">
          <span
            className="font-mono-meta px-2 py-0.5 text-[10px] font-semibold uppercase tracking-[0.06em]"
            style={{
              backgroundColor: "var(--bg-inverse)",
              color: "var(--text-inverse)",
              borderRadius: "4px",
            }}
          >
            {combo.mood_badge}
          </span>
          <span
            className="font-mono-meta px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-[0.04em]"
            style={{
              border: "1px solid var(--border-color)",
              color: "var(--text-primary)",
              backgroundColor: "var(--bg-primary)",
              borderRadius: "4px",
            }}
          >
            {formatDietaryLabel(combo.dietary_type)}
          </span>
        </div>

        <span
          className="font-mono-meta text-[12px] font-semibold uppercase tracking-[0.04em]"
          style={{ color: "var(--text-primary)" }}
        >
          {combo.restaurant.eta_mins} MINS • ₹{combo.total_price_inr}
        </span>
      </div>

      {/* Title & Restaurant */}
      <h3
        className="text-[16px] font-bold leading-snug"
        style={{ color: "var(--text-primary)" }}
      >
        {combo.title}
      </h3>
      <p
        className="mt-0.5 text-[13px] font-medium"
        style={{ color: "var(--text-secondary)" }}
      >
        {combo.restaurant.name} • ★ {combo.restaurant.rating.toFixed(1)}
      </p>

      {/* Itemized breakdown */}
      <div
        className="mt-2.5 flex flex-wrap items-center gap-x-3 gap-y-1 py-2 text-[12px]"
        style={{
          borderTop: "var(--border-hairline)",
          borderBottom: "var(--border-hairline)",
          color: "var(--text-secondary)",
        }}
      >
        {combo.items.map((item, idx) => (
          <span key={item.item_id} className="font-mono-meta">
            {idx > 0 ? "+ " : ""}
            {item.name} (₹{item.price_inr})
          </span>
        ))}
      </div>

      {/* Mood-Match Rationale */}
      <p
        className="mt-2.5 text-[13px] leading-[1.45]"
        style={{ color: "var(--text-secondary)" }}
      >
        {combo.why_it_fits}
      </p>

      {/* Single-Click Cart CTA */}
      <button
        type="button"
        disabled={adding}
        onClick={() => onAddToCart(combo)}
        className="font-mono-meta mt-3.5 w-full cursor-pointer py-2.5 text-[12px] font-semibold uppercase tracking-[0.06em] transition-colors disabled:opacity-50"
        style={{
          borderRadius: "8px",
          border: "var(--border-strong)",
          backgroundColor: added ? "var(--bg-primary)" : "var(--bg-inverse)",
          color: added ? "var(--text-primary)" : "var(--text-inverse)",
        }}
      >
        {adding
          ? "ADDING..."
          : added
            ? `✓ ADDED TO CART (₹${combo.total_price_inr}${inCartQuantity > 1 ? ` × ${inCartQuantity}` : ""})`
            : `+ ADD COMBO TO CART • ₹${combo.total_price_inr}`}
      </button>
    </article>
  );
}
