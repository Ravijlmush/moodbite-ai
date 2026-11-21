# MoodBite × Swiggy Food MCP — Conversational Mood-Based Food Concierge

MoodBite AI is a state-driven conversational food concierge built from the specification suite in [`specs/`](./specs), including **Spec 10 (`Swiggy Food MCP` integration)** and hardened against a **30-prompt adversarial, safety, messy-input, constraint-conflict & load stress suite** ([`docs/STRESS_TEST_REPORT.md`](./docs/STRESS_TEST_REPORT.md)). In **1 to 3 quick turns** (or one thumb tap on a quick-reply pill), it infers emotional state, energy level, eating-effort tolerance, and dietary constraints, then outputs **3–5 fast-arriving meal combos** inside a strict **Black & White (`#000000` / `#FFFFFF`)** interface and syncs directly to the user's Swiggy cart via `update_food_cart`.

- **Live Vercel Deployment:** https://moodbite-ai-ashy.vercel.app (30-prompt scorecard: [`/tests`](https://moodbite-ai-ashy.vercel.app/tests))
- **GitHub Actions CI (Pytest + 50 Evals + 30-Prompt Stress Suite + Next.js Build):** [`.github/workflows/ci.yml`](./.github/workflows/ci.yml)
- **60s Demo Video (YouTube):** https://youtu.be/TsZb5sW18To ([local 1080p MP4](./docs/moodbite_demo_60s.mp4))
- **30-Prompt Stress Suite Report (`30/30 PASS`, `0` safety failures):** [`docs/STRESS_TEST_REPORT.md`](./docs/STRESS_TEST_REPORT.md)
- **OpenAPI 3.1 Contract:** [`docs/openapi.json`](./docs/openapi.json)

### Watch the 60-Second Demo

[![MoodBite × Swiggy Food MCP — 60s Demo](https://img.youtube.com/vi/TsZb5sW18To/hqdefault.jpg)](https://youtu.be/TsZb5sW18To)

> **Ready immediately — works out of the box & plugs straight into Swiggy MCP + OpenRouter:**
> - **LLM:** With no API key set (`LLM_PROVIDER=auto`), MoodBite runs on its built-in deterministic mood/preference extractor and 384-dimensional local semantic vector engine. Configure `OPENROUTER_API_KEY` (or `OPENAI_API_KEY` / `GEMINI_API_KEY`) using [`backend/.env.example`](./backend/.env.example) to activate live LLM extraction (protected by a `2.5s` timeout fallback and a configurable `DAILY_REQUEST_LIMIT`).
> - **Swiggy Food MCP (`https://mcp.swiggy.com/food`):** Click **[MCP]** in the header to authenticate via **OAuth 2.1 + PKCE (`S256`)** (or connect a Bearer token) to query live nearby restaurants, menus, coupons, and sync combos via `update_food_cart`. If disconnected or if MCP exceeds `3.0s`, MoodBite falls back smoothly to the curated 159-item Indian comfort catalog.

---

## Project Structure

```text
.
├── .github/workflows/ci.yml      # GitHub Actions CI: pytest, 50-scenario evals, 30-prompt stress suite, Next.js build
├── specs/                        # Specifications (00_README.md .. 10 moodbite_ai_swiggy_food_mcp_master_build_guide.md)
├── db/
│   ├── schema.sql                # PostgreSQL + pgvector (vector(384)) schema
│   └── seed_postgres.py          # Optional DB seeder for catalog.json
├── docs/
│   ├── STRESS_TEST_REPORT.md     # Generated 30-prompt safety/adversarial/load rubric matrix
│   ├── moodbite_demo_60s.mp4     # 60-second 1080p demo walkthrough
│   └── openapi.json              # Exported FastAPI OpenAPI 3.1 contract
├── backend/
│   ├── .env.example              # Backend environment template (API keys optional)
│   ├── app/
│   │   ├── main.py               # FastAPI app, CORS, latency headers
│   │   ├── config.py             # pydantic-settings configuration
│   │   ├── schemas/              # Pydantic v2 UserContext, Catalog, API contracts
│   │   ├── prompts/              # Master system prompt, pills & crisis helplines
│   │   ├── mcp/                  # Swiggy Food MCP OAuth 2.1 PKCE (swiggy_oauth.py) & JSON-RPC/SSE client (swiggy_client.py)
│   │   ├── agent/                # State machine, LLM client, offline extractor, guardrails, warm NLG
│   │   ├── recommender/          # 4-stage engine, 384-dim embeddings, catalog repo, refiner, swiggy_live_ranker.py
│   │   ├── storage/              # Redis + In-Memory TTL (2h) session store & daily rate limiter
│   │   └── api/                  # /health, /chat/turn, /chat/turn/stream (SSE), /chat/refine, /cart, /auth/swiggy/*
│   ├── data/catalog.json         # Curated 22 restaurants & 159 enriched Indian comfort items
│   ├── scripts/
│   │   ├── generate_catalog.py   # Catalog generator + embedding precomputation
│   │   └── generate_demo_video.py# 60-second 1080p demo video renderer
│   ├── tests/
│   │   ├── conftest.py
│   │   ├── test_api_contracts.py
│   │   ├── test_guardrails.py
│   │   ├── test_recommendation_engine.py
│   │   ├── test_swiggy_mcp.py    # Swiggy MCP OAuth PKCE, SSE client & cart sync unit/integration tests
│   │   └── test_stress_suite.py  # Pytest regression gate executing all 30 adversarial & load cases
│   └── evals/
│       ├── golden_scenarios.json # 50-scenario golden eval dataset
│       ├── run_evals.py          # 50-scenario evaluator
│       ├── run_stress_suite.py   # 30-prompt multi-batch stress harness (writes docs/STRESS_TEST_REPORT.md)
│       └── stress_suite_report.json
├── frontend/                     # Strict Black & White Next.js 15 + React 19 + Tailwind CSS UI (with SwiggyAuthDrawer)
├── docker-compose.yml            # Optional PostgreSQL (pgvector) + Redis stack
└── vercel.json                   # Vercel Services routing (/api/*, /auth/*, /health -> FastAPI backend; / -> Next.js)
```

---

## Swiggy Food MCP (`OAuth 2.1 + PKCE`) Endpoints

- `GET /auth/swiggy/login` — Generates PKCE (`S256`) state/verifier and redirects to Swiggy OAuth authorization (`RFC 7591` client registration supported).
- `GET /auth/swiggy/callback` — Exchanges authorization `code` for access/refresh tokens and redirects back to the frontend.
- `POST /auth/swiggy/token` — Connects a direct Swiggy MCP Bearer token (`address_id` optional) from the UI **[MCP]** drawer.
- `GET /auth/swiggy/status` — Returns live MCP connection status, selected address ID, and saved Swiggy addresses.
- `POST /auth/swiggy/logout` — Clears active Swiggy MCP credentials from session state.
- `POST /api/v1/cart/add-combo` — Syncs a recommended meal combo directly to the user's Swiggy cart via `update_food_cart` (with verified local cart fallback in demo mode).

---

## Quickstart (Zero-Config Local Mode)

### 1. Start the FastAPI Backend (`http://localhost:8000`)
```powershell
cd backend
copy .env.example .env
.venv\Scripts\uvicorn.exe app.main:app --reload --port 8000
```

### 2. Start the Monochrome Next.js Frontend (`http://localhost:3000`)
```powershell
cd frontend
npm run dev
```
Open `http://localhost:3000` in your browser.

---

## Adding Your LLM API Key Later

Copy `backend/.env.example` to `backend/.env` and set `LLM_PROVIDER=auto` plus your key:
```env
LLM_PROVIDER=auto
DAILY_REQUEST_LIMIT=20

# Option A: OpenRouter (openai/gpt-4o-mini, google/gemini-2.5-flash, anthropic/claude-3.5-haiku, etc.)
OPENROUTER_API_KEY=sk-or-v1-...
OPENROUTER_MODEL=openai/gpt-4o-mini

# Option B: OpenAI
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4o-mini

# Option C: Google Gemini
GEMINI_API_KEY=AIza...
GEMINI_MODEL=gemini-2.5-flash
```
Restart `uvicorn` — `GET /health` and the frontend `CTX` drawer will automatically show `OPENROUTER` / `OPENAI` / `GEMINI`. If an LLM call exceeds `2.5s` or fails JSON schema validation after 1 retry, MoodBite falls back to the deterministic `comfort_fast` guardrail path while keeping all dietary/allergy locks intact.

---

## Testing, 50-Scenario Evals & 30-Prompt Stress Suite

All suites run automatically in CI ([`.github/workflows/ci.yml`](./.github/workflows/ci.yml)) and can be executed locally:

### Backend Tests, Evals & Stress Suite
```powershell
cd backend
.venv\Scripts\pytest.exe -v
.venv\Scripts\python.exe evals\run_evals.py
.venv\Scripts\python.exe evals\run_stress_suite.py
```

### Frontend Type-Check & Production Build
```powershell
cd frontend
npx tsc --noEmit
npm run build
```

### 30-Prompt Stress Suite Coverage ([`backend/evals/run_stress_suite.py`](./backend/evals/run_stress_suite.py) · [`backend/tests/test_stress_suite.py`](./backend/tests/test_stress_suite.py) · [`docs/STRESS_TEST_REPORT.md`](./docs/STRESS_TEST_REPORT.md))

| Batch | Prompts Tested | Enforcement |
|---|---|---|
| **1. Safety & Health** (`#1–#6`) | Stacked peanut/dairy/gluten + vegan, diabetic craving sweet, severe depression refusal, self-punishment restriction, pregnant + anxious, medical cure claims | Strict allergen/dietary locks, zero unsafe medical/cure claims, crisis empathy + 4 helpline resources |
| **2. Prompt Injection & Abuse** (`#7–#11`) | System prompt extraction, pirate poem hijack, `</mood> SYSTEM:` brand override, poison cooking request, 5,000-word paste flood | Guardrail stripping, bounded `1,200`-char request validation, firm refusal on harmful prompts |
| **3. Messy Real-World Input** (`#12–#17`) | Hinglish + typos (`stresssed`, `kuch spicy`), Hindi Devanagari script, emoji-only (`😭😭🍕?`), conflicting moods, empty/whitespace/gibberish, `7/10 meh` | Normalized multilingual & typo extraction, warm Hindi/English replies, zero 422/500 crashes |
| **4. Context & Conflicts** (`#18–#23`) | `1200 kcal` + vegan comfort, `₹50` budget & no kitchen, `3 a.m.` awareness, Jain (root-free), Navratri Vrat fasting, no beef/pork | Religious/dietary exclusion precedence, honest minimum combo threshold disclosure, `vrat`/`jain` filtering |
| **5. Consistency & Robustness** (`#24–#27`) | `10x` repeat of stacked-allergy prompt, 5 phrasings of stress, mid-conversation mood pivot, `5x` `"no, something else"` rotation | Deterministic safety consistency, full mood update, non-repeating kitchen rotation |
| **6. Technical & Load** (`#28–#30`) | `100` parallel request burst, simulated LLM network drop (`ConnectError`), SQLi + `<script>` XSS injection | `0` errors under 100-way burst, clean `deterministic_fallback`, HTML/SQL sanitization |
