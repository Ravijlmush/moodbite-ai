# 07 — Engineering Rules & Safety Guardrails (`RULES.md`)

## 1. Product & Conversational Guardrails (Non-Negotiable)
1. **The 3-Turn Ceiling Rule:** The agent MUST NEVER ask more than 2 clarifying questions. On Turn 3 (or earlier if confidence `>= 0.75`), it MUST output `action = "recommend_combos"` with at least 3 valid meal combos.
2. **Zero-Hallucination Catalog Rule:** The LLM is strictly forbidden from inventing dish names, prices, restaurant names, or delivery ETAs. Every combo returned to the UI MUST come from verified database records returned by the Recommendation Engine.
3. **Dietary & Allergy Lock Rule:** Once a user states a dietary preference (`veg`, `vegan`, `jain`, `halal`) or an allergy (`peanuts`, `dairy`, `gluten`), it becomes an immutable hard filter in `UserContext.hard_constraints` for the entire session unless the user explicitly cancels it.
4. **Medical & Mental Health Boundary Rule:**
   - MoodBite is a culinary mood-matching concierge, NOT a medical or mental health tool.
   - Never diagnose depression, anxiety, or eating disorders.
   - If a user expresses severe self-harm or crisis language, bypass food recommendations immediately and display standard crisis helpline support resources.
5. **No Shaming / Moralizing Food Rule:** Never lecture the user about sugar, calories, or "junk food" when they ask for comfort food like Coke or Gulab Jamun. Offer balanced options subtly via refinement chips (*"Something lighter"*) without judgment.

## 2. UI/UX Enforcement Rules (Black & White Strictness)
1. **Strict Monochrome Palette:** Only `#000000`, `#FFFFFF`, and neutral grayscale steps (`#121212`, `#262626`, `#525252`, `#E5E5E5`, `#F7F7F7`) are permitted in CSS/Tailwind configs. Do NOT introduce red, green, yellow, or brand accent colors—even for star ratings or dietary icons (use bordered `[VEG]` / `[NON-VEG]` monochrome badges).
2. **Zero Drop-Shadow Rule:** Use `1px` or `1.5px` solid borders (`#000000` or `#E5E5E5`) for card separation instead of box shadows.
3. **Thumb-Friendly Action Density:** Every agent turn MUST render 3–4 quick-reply pills (`min-height: 36px`) so a tired user can complete the flow without typing.

## 3. Codebase & AI Coding Agent Conventions
1. **Strict Typing & Validation:** All backend request/response payloads and LLM structured outputs MUST be validated using **Pydantic v2** schemas. Never pass raw unparsed LLM strings to the frontend.
2. **Separation of Concerns:** Keep LLM prompt templates (`prompts/`), state machine routing (`agent/`), deterministic SQL/vector ranking (`recommender/`), and API routes (`api/`) in isolated modules.
3. **Deterministic Fallbacks:** If the LLM extractor times out (`> 2.5s`) or fails schema validation after 1 retry, fall back gracefully to a default `comfort_fast` state (`max_eta_mins = 30`, `effort_to_eat = "zero_mess"`) so the hungry user still gets instant food recommendations.
4. **Environment & Secrets:** Never hardcode API keys or DB credentials; load all configuration via `.env` and `pydantic-settings`.
