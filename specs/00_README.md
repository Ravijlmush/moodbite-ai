# MoodBite AI — Conversational Mood-Based Food Delivery Agent

## Overview
MoodBite AI is an autonomous, state-driven conversational food recommendation agent designed for food delivery platforms (such as Zomato). Rather than forcing hungry, mentally fatigued users to scroll through thousands of menu items, MoodBite engages in a rapid **2-to-3 turn natural conversation** to infer emotional state, energy level, situational context, and delivery urgency—then outputs a curated list of **3–5 fast-arriving meal combos** with mood-match explanations and one-tap adjustment chips.

## Design Philosophy
- **Empathy First, Friction Zero:** Users opening a food app while stressed, exhausted, or upset need warmth and speed—not an interrogation or a clinical therapy session.
- **High-Contrast Monochrome UI:** Strict `#000000` (pure black) and `#FFFFFF` (pure white) interface with crisp `1px` borders, zero visual noise, and instant scannability.
- **Deterministic Guardrails + LLM Empathy:** The LLM handles conversational warmth and structured state extraction; deterministic backend rules enforce dietary restrictions, allergy safety, live ETA filtering (`<= 30 mins`), and combo pairing logic.

## Specification Suite Index
| File | Purpose |
| :--- | :--- |
| `00_README.md` | Project overview, repository map, and quickstart guide for AI coding agents. |
| `01_PRD.md` | Product Requirements Document: problem statement, user personas, functional scope, non-goals, and KPIs. |
| `02_ARCHITECTURE.md` | End-to-end system architecture, hybrid LLM + deterministic pipeline, latency budgets, and data flow. |
| `03_AGENT_PROMPTS_AND_SCHEMA.md` | Master conversational system prompt, few-shot dialogue examples, `UserContext` JSON schema, and state transition rules. |
| `04_RECOMMENDATION_ENGINE.md` | Offline menu/combo enrichment schema, multi-factor mood scoring formula, combo pairing rules, and live logistics filters. |
| `05_UI_UX_BLACK_AND_WHITE.md` | Complete monochrome (`#000000` / `#FFFFFF`) design system, CSS variables, component specs, and mobile wireframes. |
| `06_API_AND_DATABASE.md` | REST/SSE API contracts, PostgreSQL/pgvector schema, Redis session state store, and error payloads. |
| `07_RULES_AND_GUARDRAILS.md` | Non-negotiable engineering rules, AI coding agent conventions, dietary/medical safety guardrails, and prompt hygiene. |
| `08_TESTING_AND_EVALS.md` | Evaluation harness, synthetic mood-scenario test suite, guardrail regression tests, and latency benchmarks. |
| `09_ROADMAP.md` | Phased execution plan from MVP prototype to production rollout. |

## Recommended Tech Stack
- **Backend:** Python 3.11+, FastAPI, Pydantic v2, AsyncIO
- **LLM & State Extraction:** Structured JSON output via OpenAI / Gemini / local quantized LLM (`Ollama` / `llama.cpp`)
- **Database & Retrieval:** PostgreSQL + `pgvector` (semantic mood-food similarity) + Redis (ephemeral session `UserContext`)
- **Frontend:** Next.js / React + Tailwind CSS (strict monochrome palette)
