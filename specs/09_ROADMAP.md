# 09 — Implementation Roadmap

## Phase 1: Core State Machine & Mock Catalog Prototype (Days 1–3)
- Implement `UserContext` Pydantic v2 schema and FastAPI `/chat/turn` endpoint.
- Build the 3-turn conversational prompt with structured JSON output.
- Seed a curated local dataset of 150 Indian comfort/mood dishes & beverages with pre-computed mood tags and pairing affinities.

## Phase 2: Monochrome Black & White Chat UI (Days 4–6)
- Build mobile-first Next.js/React chat interface adhering strictly to `05_UI_UX_BLACK_AND_WHITE.md`.
- Implement streaming agent messages, quick-reply pills, combo cards, and one-tap refinement chips.
- Wire single-click `+ ADD COMBO TO CART` state updates.

## Phase 3: Hybrid `pgvector` Retrieval & Live Logistics (Days 7–10)
- Add `pgvector` embeddings (`bge-small-en-v1.5`) for semantic mood-to-dish matching.
- Integrate live ETA filtering, restaurant deduplication, and multi-objective combo scoring.

## Phase 4: Eval Harness & Production Hardening (Days 11–14)
- Run automated `pytest` guardrail suite (dietary lock, 3-turn ceiling, zero-hallucination checks).
- Add Redis session persistence, timeout fallbacks, and latency telemetry.
