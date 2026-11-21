# 01 — Product Requirements Document (PRD)

## 1. Problem Statement
Conventional food delivery interfaces rely on search bars, cuisine filters, and endless restaurant feeds. When a user is emotionally drained, stressed after work/study, or unwell, **decision fatigue** peaks. Asking them to browse 40 restaurants and assemble a main dish plus a drink leads to cart abandonment or settling for unsatisfying food.

## 2. Product Vision
Build an embedded conversational concierge (**MoodBite AI**) inside a food delivery app that:
1. Greets the user like a perceptive friend in **2–3 lightweight turns**.
2. Extracts mood, energy level, hunger intensity, eating effort tolerance (`zero-mess` vs. full meal), and time/budget constraints.
3. Recommends **3 to 5 ready-to-order meal combos** (e.g., *Homestyle Rajma Chawal Bowl + Chilled Coke*) available nearby with fast delivery (`<= 30 mins`), explaining *why* each combo matches their current state.

## 3. Target User Personas
| Persona | Emotional & Situational State | Food Need | Example Trigger |
| :--- | :--- | :--- | :--- |
| **The Burned-Out Worker / Student** | Mentally exhausted, low patience, mild stress | Warm, nostalgic, zero-mess bowl + fizzy/sweet pick-me-up | *"Super tired and mood is off, just want something fast that cheers me up."* |
| **The Overwhelmed & Stressed** | High cortisol, tense, needs sensory release | Bold, spicy, crunchy flavors or hearty comfort | *"Had an awful meeting, need spicy comfort food right now."* |
| **The Sluggish / Post-Illness User** | Low appetite, heavy stomach, tired | Light, warm, easy-to-digest comfort | *"Feeling drained and heavy, nothing too oily."* |
| **The Celebratory / Chill User** | Upbeat, relaxed, wants indulgence | Shareable/treat combos, dessert pairings | *"Finally finished exams! Want something fun to celebrate."* |

## 4. Functional Requirements
### FR-1: Multi-Turn Empathetic Warm-Up
- **FR-1.1:** Agent MUST initiate with a casual, low-friction check-in (never a cold search prompt or clinical interrogation).
- **FR-1.2:** Agent MUST reach a recommendation state within **1 to 3 user turns** (hard ceiling: 3 turns before showing a curated list).
- **FR-1.3:** Every agent message MUST include **3–4 tappable quick-reply pills** so low-energy users can respond with one thumb tap.

### FR-2: Hidden State Extraction (`UserContext`)
- **FR-2.1:** On every turn, the agent updates a structured `UserContext` object tracking `mood`, `energy_level`, `craving_profile`, `effort_to_eat`, `dietary_constraints`, `budget_inr`, and `max_eta_mins`.
- **FR-2.2:** Explicit dietary rules (e.g., `veg`, `jain`, `no_dairy`, `nut_allergy`) persist across all turns unless explicitly overridden.

### FR-3: Combo-First Recommendation List
- **FR-3.1:** Output **3 to 5 complete meal combos** (Main + Beverage/Side) rather than isolated ingredients.
- **FR-3.2:** Each recommendation card MUST display: Combo Title, Restaurant Name, Live ETA (mins), Price (INR), Mood-Match Tag, and a **1-sentence personalized reason** tied to the user's state.
- **FR-3.3:** Provide **one-tap refinement chips** below the list (*"Spicier"*, *"Lighter"*, *"Under ₹250"*, *"Swap Drink"*).

## 5. Non-Goals (Out of Scope for v1)
- Long-term mental health journaling or clinical nutritional/medical diagnosis.
- Multi-restaurant split carts within a single combo.
- Voice-to-voice real-time audio streaming (text + quick-reply chips only in v1).

## 6. Success Metrics (KPIs)
- **Conversation-to-Cart Conversion Rate:** `>= 28%` of sessions result in an `Add Combo to Cart` click.
- **Turns to First Recommendation:** Median `<= 2.2 turns`.
- **Time to First Token (TTFT):** `<= 600 ms`; full turn latency `<= 1.8 s`.
- **Dietary Violation Rate:** `0.0%` (enforced deterministically).
