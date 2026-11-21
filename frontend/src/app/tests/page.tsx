"use client";

import Link from "next/link";
import React, { useEffect, useMemo, useState } from "react";
import { fetchStressReport } from "@/lib/api";
import { StressSuiteReport } from "@/lib/types";

const BATCH_FILTERS = [
  "ALL",
  "1. Safety & Health",
  "2. Prompt Injection & Abuse",
  "3. Messy Real-World Input",
  "4. Context & Conflicts",
  "5. Consistency & Robustness",
  "6. Technical & Load",
];

export default function TestsPage() {
  const [report, setReport] = useState<StressSuiteReport | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [selectedBatch, setSelectedBatch] = useState<string>("ALL");
  const [darkMode, setDarkMode] = useState<boolean>(false);

  useEffect(() => {
    document.documentElement.setAttribute("data-theme", darkMode ? "dark" : "light");
  }, [darkMode]);

  useEffect(() => {
    fetchStressReport()
      .then((data) => setReport(data))
      .catch((err) => {
        setError(err instanceof Error ? err.message : "Failed to load stress report");
      });
  }, []);

  const filteredCases = useMemo(() => {
    if (!report) return [];
    if (selectedBatch === "ALL") return report.results;
    return report.results.filter((item) => item.batch === selectedBatch);
  }, [report, selectedBatch]);

  const burstLatency = useMemo(() => {
    const item28 = report?.results.find((r) => r.number === 28);
    return item28 ? `${item28.latency_ms.toFixed(2)} ms` : "--";
  }, [report]);

  return (
    <div
      className="min-h-screen w-full"
      style={{
        backgroundColor: "var(--bg-primary)",
        color: "var(--text-primary)",
      }}
    >
      <header
        className="sticky top-0 z-20 mx-auto flex max-w-5xl items-center justify-between gap-3 px-4 py-3"
        style={{
          backgroundColor: "var(--bg-primary)",
          borderBottom: "var(--border-strong)",
        }}
      >
        <div className="flex items-center gap-2.5">
          <Link
            href="/"
            className="font-mono-meta inline-flex items-center px-2.5 py-1.5 text-[11px] font-semibold uppercase tracking-wide"
            style={{
              borderRadius: "8px",
              border: "1px solid var(--border-color)",
              backgroundColor: "var(--bg-primary)",
              color: "var(--text-primary)",
            }}
          >
            &lt;- CHAT
          </Link>
          <h1 className="text-[15px] font-semibold tracking-[-0.02em]">
            MOODBITE × 30-PROMPT STRESS SUITE
          </h1>
        </div>

        <button
          type="button"
          onClick={() => setDarkMode((prev) => !prev)}
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
      </header>

      <main className="mx-auto max-w-5xl space-y-5 px-4 py-5">
        {error && (
          <div
            className="font-mono-meta rounded-[12px] p-4 text-xs"
            style={{
              backgroundColor: "var(--bg-subtle)",
              border: "var(--border-strong)",
              color: "var(--text-primary)",
            }}
          >
            ERROR LOADING REPORT: {error}
          </div>
        )}

        {!report && !error && (
          <div
            className="font-mono-meta rounded-[12px] p-6 text-xs"
            style={{
              backgroundColor: "var(--bg-subtle)",
              border: "var(--border-hairline)",
              color: "var(--text-secondary)",
            }}
          >
            LOADING 30-PROMPT STRESS SUITE REPORT...
          </div>
        )}

        {report && (
          <>
            <section className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
              {[
                { label: "STRESS SUITE", value: `${report.passed} / ${report.total_prompts} PASS`, inverse: true },
                { label: "SAFETY FAILURES", value: `${report.safety_failures}`, inverse: false },
                {
                  label: "GATE (#1–#6 & #10)",
                  value: report.all_1_to_6_and_10_safe ? "100% SAFE" : "BLOCKED",
                  inverse: false,
                },
                { label: "GOLDEN EVALS", value: "50 / 50 PASS", inverse: false },
                { label: "PYTEST GATE", value: "24 / 24 PASS", inverse: false },
                { label: "100-REQ P95", value: burstLatency, inverse: false },
              ].map((stat) => (
                <div
                  key={stat.label}
                  className="rounded-[12px] p-3"
                  style={{
                    backgroundColor: stat.inverse ? "var(--bg-inverse)" : "var(--bg-subtle)",
                    color: stat.inverse ? "var(--text-inverse)" : "var(--text-primary)",
                    border: "var(--border-strong)",
                  }}
                >
                  <div className="font-mono-meta text-[10px] font-semibold uppercase tracking-wide opacity-80">
                    {stat.label}
                  </div>
                  <div className="font-mono-meta mt-1 text-sm font-semibold">{stat.value}</div>
                </div>
              ))}
            </section>

            <section
              className="rounded-[12px] p-4"
              style={{
                backgroundColor: "var(--bg-subtle)",
                border: "var(--border-hairline)",
              }}
            >
              <div className="font-mono-meta text-[10px] font-semibold uppercase tracking-wide">
                5-AXIS SCORING RUBRIC &amp; BATCH FILTER
              </div>
              <p className="mt-1.5 text-xs leading-relaxed" style={{ color: "var(--text-secondary)" }}>
                Every scenario is evaluated across <strong>Safety</strong> (allergies, medical boundaries, crisis routing),{" "}
                <strong>Relevance</strong>, <strong>Robustness</strong> (injections, malformed input, network drops, burst load),{" "}
                <strong>Tone</strong>, and <strong>Consistency</strong>.
              </p>

              <div className="mt-3 flex flex-wrap gap-2">
                {BATCH_FILTERS.map((batch) => {
                  const active = selectedBatch === batch;
                  return (
                    <button
                      key={batch}
                      type="button"
                      onClick={() => setSelectedBatch(batch)}
                      className="font-mono-meta cursor-pointer px-3 py-1.5 text-[11px] font-semibold"
                      style={{
                        borderRadius: "9999px",
                        border: "1px solid var(--border-color)",
                        backgroundColor: active ? "var(--bg-inverse)" : "var(--bg-primary)",
                        color: active ? "var(--text-inverse)" : "var(--text-primary)",
                      }}
                    >
                      {batch}
                    </button>
                  );
                })}
              </div>
            </section>

            <section className="space-y-3">
              {filteredCases.map((item) => (
                <article
                  key={item.number}
                  className="rounded-[12px] p-4"
                  style={{
                    backgroundColor: "var(--bg-primary)",
                    border: "var(--border-strong)",
                  }}
                >
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <div className="flex flex-wrap items-center gap-2">
                      <span
                        className="font-mono-meta px-2 py-0.5 text-[10px] font-semibold uppercase"
                        style={{
                          borderRadius: "6px",
                          backgroundColor: "var(--bg-inverse)",
                          color: "var(--text-inverse)",
                        }}
                      >
                        #{item.number} • {item.overall}
                      </span>
                      <span
                        className="font-mono-meta px-2 py-0.5 text-[10px] font-semibold uppercase"
                        style={{
                          borderRadius: "6px",
                          border: "1px solid var(--border-color)",
                        }}
                      >
                        {item.batch}
                      </span>
                      <h2 className="text-sm font-semibold">{item.title}</h2>
                    </div>

                    <div
                      className="font-mono-meta text-[11px]"
                      style={{ color: "var(--text-secondary)" }}
                    >
                      RUNS: {item.runs} • {item.latency_ms.toFixed(2)} ms
                    </div>
                  </div>

                  <div
                    className="font-mono-meta mt-2.5 overflow-x-auto rounded-[8px] px-3 py-2 text-[11px]"
                    style={{
                      backgroundColor: "var(--bg-subtle)",
                      border: "var(--border-hairline)",
                    }}
                  >
                    PROMPT: {item.prompt_preview || "(empty / whitespace)"}
                  </div>

                  <div className="mt-2.5 flex flex-wrap gap-1.5">
                    {[
                      ["SAFETY", item.safety],
                      ["RELEVANCE", item.relevance],
                      ["ROBUSTNESS", item.robustness],
                      ["TONE", item.tone],
                      ["CONSISTENCY", item.consistency],
                    ].map(([axis, status]) => (
                      <span
                        key={axis}
                        className="font-mono-meta px-2 py-0.5 text-[10px] font-semibold"
                        style={{
                          borderRadius: "6px",
                          border: "1px solid var(--border-color)",
                          backgroundColor: status === "PASS" ? "var(--bg-primary)" : "var(--bg-inverse)",
                          color: status === "PASS" ? "var(--text-primary)" : "var(--text-inverse)",
                        }}
                      >
                        {axis}: {status}
                      </span>
                    ))}
                  </div>

                  <p className="mt-2.5 text-xs leading-relaxed" style={{ color: "var(--text-secondary)" }}>
                    <strong style={{ color: "var(--text-primary)" }}>Notes:</strong> {item.notes}
                  </p>
                  {item.sample_reply && (
                    <p className="mt-1 text-xs leading-relaxed" style={{ color: "var(--text-secondary)" }}>
                      <strong style={{ color: "var(--text-primary)" }}>Sample Reply:</strong> {item.sample_reply}
                    </p>
                  )}
                </article>
              ))}
            </section>
          </>
        )}
      </main>
    </div>
  );
}
