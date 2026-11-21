# 02 — System Architecture

## 1. Architectural Pattern: Hybrid Conversational State Machine
Pure LLM pipelines fail in food delivery because they hallucinate menu availability, violate dietary constraints, or recommend restaurants 55 minutes away. MoodBite separates **empathy & intent parsing** (LLM) from **logistics & catalog ranking** (Deterministic Engine).

```
+-------------------------------------------------------------------+
|                     MONOCHROME CLIENT UI (B&W)                    |
|   Chat Stream  |  Quick-Reply Pills  |  Combo Cards & Cart CTA    |
+---------------------------------+---------------------------------+
                                  | HTTPS / SSE Stream
                                  v
+-------------------------------------------------------------------+
|                   ORCHESTRATOR SERVICE (FastAPI)                  |
|                                                                   |
|  1. Load Session State (Redis: UserContext + Chat History)        |
|  2. LLM State Extractor & Dialogue Planner (Structured JSON)      |
|  3. Decision Gate:                                                |
|     +-- [confidence < 0.75 AND turn < 3] --> Emit Micro-Probe     |
|     +-- [confidence >= 0.75 OR turn == 3] --> Trigger Engine      |
+---------------------------------+---------------------------------+
                                  |
                                  v
+-------------------------------------------------------------------+
|               DETERMINISTIC RECOMMENDATION ENGINE                 |
|                                                                   |
|  Step A: Hard Filter (Serviceable Radius, ETA <= 30m, Veg/Allergy)|
|  Step B: Hybrid Retrieval (pgvector Mood Embedding + Tag Match)   |
|  Step C: Combo Assembler (Main Bowl/Roll + Dopamine Drink/Side)   |
|  Step D: Multi-Objective Re-Ranker (MoodFit + ETA + Rating)       |
+---------------------------------+---------------------------------+
                                  |
                                  v
+-------------------------------------------------------------------+
|                  RESPONSE GENERATOR (LLM NLG)                     |
|  Wraps top 3-5 combos in warm, concise copy + refinement chips    |
+-------------------------------------------------------------------+
```

## 2. Component Responsibilities
1. **Session Store (Redis):** Stores `session_id`, `turn_count`, `chat_history` (last 8 messages), and `UserContext` JSON with a 2-hour TTL.
2. **LLM State Extractor:** Uses strict JSON Schema / Pydantic structured outputs to update `UserContext` and decide whether to ask 1 clarifying micro-probe or trigger `recommend_combos`.
3. **Catalog & Logistics Service (PostgreSQL + PostGIS/pgvector):**
   - Pre-enriched menu items with offline mood/texture embeddings (`384-dim` `bge-small` or `e5-small`).
   - Real-time restaurant availability, prep time, and rider ETA filtering.
4. **Combo Assembler:** Pairs a primary dish (`effort_to_eat = zero_mess` when user is tired) with a complementary beverage or dessert from the **same restaurant** to keep delivery single-origin and fast.

## 3. Latency Budget (End-to-End Target: < 1,800 ms)
- Redis state fetch & write: `< 15 ms`
- LLM State Extraction (JSON mode): `450 – 700 ms`
- PostgreSQL hard filter + `pgvector` ANN search + combo scoring: `60 – 120 ms`
- Streaming NLG response first token: `350 – 500 ms`
