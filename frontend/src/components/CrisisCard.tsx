"use client";

import React from "react";
import { CrisisResource } from "@/lib/types";

interface CrisisCardProps {
  resources: CrisisResource[];
}

export function CrisisCard({ resources }: CrisisCardProps) {
  if (!resources || resources.length === 0) return null;

  return (
    <div
      className="mt-3 p-4"
      style={{
        backgroundColor: "var(--bg-subtle)",
        border: "var(--border-strong)",
        borderRadius: "var(--radius-card)",
      }}
    >
      <p
        className="font-mono-meta mb-2.5 text-[11px] font-semibold uppercase tracking-[0.08em]"
        style={{ color: "var(--text-primary)" }}
      >
        IMMEDIATE SUPPORT HELPLINES
      </p>
      <div className="flex flex-col gap-2.5">
        {resources.map((res) => (
          <div
            key={res.name}
            className="p-3"
            style={{
              backgroundColor: "var(--bg-primary)",
              border: "1px solid var(--border-color)",
              borderRadius: "8px",
            }}
          >
            <div className="flex items-center justify-between gap-2">
              <p
                className="text-[14px] font-bold"
                style={{ color: "var(--text-primary)" }}
              >
                {res.name}
              </p>
              <span
                className="font-mono-meta px-1.5 py-0.5 text-[10px] font-semibold uppercase"
                style={{
                  border: "1px solid var(--border-color)",
                  color: "var(--text-primary)",
                  borderRadius: "4px",
                }}
              >
                {res.region}
              </span>
            </div>
            <p
              className="font-mono-meta mt-1 text-[13px] font-semibold"
              style={{ color: "var(--text-primary)" }}
            >
              {res.contact}
            </p>
            <p
              className="mt-0.5 text-[12px]"
              style={{ color: "var(--text-secondary)" }}
            >
              {res.availability}
            </p>
          </div>
        ))}
      </div>
    </div>
  );
}
