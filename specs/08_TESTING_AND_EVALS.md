# 08 — Testing & Evaluation Suite

## 1. Automated Guardrail & Unit Tests (`pytest`)
- **`test_dietary_persistence`:** User specifies `"veg"` in Turn 1, then says `"surprise me with something spicy"` in Turn 2 -> Assert `0` non-veg/egg items appear in recommendations.
- **`test_turn_ceiling`:** Simulate 3 consecutive ambiguous user replies (`"idk"`, `"anything"`, `"whatever"`) -> Assert Turn 3 forces `action == "recommend_combos"` with `>= 3` combos.
- **`test_eta_constraint`:** User states `"super tired, need it fast"` -> Assert all returned combos have `eta_mins <= 30`.
- **`test_no_hallucinated_items`:** Assert every `item_id` and `restaurant_id` in `/api/v1/chat/turn` exists in PostgreSQL and belongs to the same restaurant.

## 2. Conversational Mood Evaluation Scenarios (Golden Dataset)
Run 50 synthetic multi-turn personas through an LLM-as-a-Judge evaluator scoring **Empathy (1–5)**, **Brevity (< 45 words)**, and **Combo Relevance (1–5)**:
1. *Exhausted late-night coder wanting fast comfort (`Rajma Chawal + Coke`).*
2. *Heartbroken/low-mood user wanting warm nostalgic dessert pairing.*
3. *Stressed pre-exam student needing crunchy/spicy release without mess.*
4. *Post-fever user with low appetite needing light curd rice / soup.*
5. *Budget-constrained user (`under ₹200`) wanting a filling mood booster.*

## 3. Performance Benchmarks
- **P95 End-to-End Turn Latency:** `< 1,800 ms`
- **P99 Recommendation Engine Query Time:** `< 120 ms`
- **JSON Schema Parse Success Rate:** `>= 99.8%`
