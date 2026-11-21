# MoodBite × Swiggy Food MCP — Conversational Mood-Based Food Concierge

MoodBite AI is a state-driven conversational food concierge built from the specification suite in [`specs/`](./specs), including **Spec 10 (`Swiggy Food MCP` integration)** and hardened against a 30-prompt adversarial & load stress suite ([`docs/STRESS_TEST_REPORT.md`](./docs/STRESS_TEST_REPORT.md)). In **1 to 3 quick turns** (or one thumb tap on a quick-reply pill), it infers emotional state, energy level, eating-effort tolerance, and dietary constraints, then outputs **3–5 fast-arriving meal combos** inside a strict **Black & White (`#000000` / `#FFFFFF`)** interface and syncs directly to the user's Swiggy cart via `update_food_cart`.

> **Ready immediately — works out of the box & plugs straight into Swiggy MCP + OpenRouter:**
> - **LLM:** With no API key set (`LLM_PROVIDER=auto`), MoodBite runs on its built-in deterministic mood/preference extractor and 384-dimensional local semantic vector engine. Paste `OPENROUTER_API_KEY` (or `OPENAI_API_KEY` / `GEMINI_API_KEY`) into [`backend/.env`](./backend/.env) to activate live LLM extraction (protected by a `2.5s` timeout fallback and a `DAILY_REQUEST_LIMIT=20` quota).
> - **Swiggy Food MCP (`https://mcp.swiggy.com/food`):** Click **[MCP]** in the header to authenticate via **OAuth 2.1 + PKCE (`S256`)** (or paste a Bearer token) to query live nearby restaurants, menus, coupons, and sync combos via `update_food_cart`. If disconnected or if MCP exceeds `3.0s`, MoodBite falls back smoothly to the curated 159-item Indian comfort catalog.

---

## 60-Second Demo & Reports

- **60s 1080p Demo Video:** [`docs/moodbite_demo_60s.mp4`](./docs/moodbite_demo_60s.mp4)
- **30-Prompt Stress Suite Report:** [`docs/STRESS_TEST_REPORT.md`](./docs/STRESS_TEST_REPORT.md) (`30/30 PASS`, `0` safety failures)
- **OpenAPI 3.1 Contract:** [`docs/openapi.json`](./docs/openapi.json)

---

## Project Structure

```text
.
├── specs/                        # Extracted specification files (00_README.md .. 09_ROADMAP.md)
├── db/
│   ├── schema.sql                # PostgreSQL + pgvector (vector(384)) schema
│   └── seed_postgres.py          # Optional DB seeder for catalog.json
├── docs/
│   └── openapi.json              # Exported FastAPI OpenAPI 3.1 contract
├── backend/
│   ├── .env                      # Local runtime config (API keys optional)
│   ├── app/
│   │   ├── main.py               # FastAPI app, CORS, latency headers
│   │   ├── config.py             # pydantic-settings configuration
│   │   ├── schemas/              # Pydantic v2 UserContext, Catalog, API contracts
│   │   ├── prompts/              # Master system prompt, pills & crisis helplines
│   │   ├── agent/                # State machine, LLM client, offline extractor, guardrails, NLG
│   │   ├── recommender/          # 4-stage engine, 384-dim embeddings, catalog repo, refiner
│   │   ├── storage/              # Redis + In-Memory TTL (2h) session store
│   │   └── api/                  # /health, /chat/turn, /chat/turn/stream (SSE), /chat/refine, /cart
│   ├── data/catalog.json         # Curated 22 restaurants & 155 enriched Indian comfort items
│   ├── scripts/generate_catalog.py
│   ├── tests/                    # Automated pytest guardrail, engine & API tests
│   └── evals/                    # 50-scenario golden dataset & evaluator
├── frontend/                     # Strict Black & White Next.js 15 + React 19 + Tailwind CSS UI
├── docker-compose.yml            # Optional PostgreSQL (pgvector) + Redis stack
└── MoodBite_AI_Complete_Specs.zip
```

---

## Quickstart (Zero-Config Local Mode)

### 1. Start the FastAPI Backend (`http://localhost:8000`)
```powershell
cd backend
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

Edit [`backend/.env`](./backend/.env):
```env
LLM_PROVIDER=auto

# Option A: OpenRouter (works with openai/gpt-4o-mini, google/gemini-2.5-flash, anthropic/claude-3.5-haiku, etc.)
OPENROUTER_API_KEY=sk-or-v1-...
OPENROUTER_MODEL=openai/gpt-4o-mini

# Option B: OpenAI
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4o-mini

# Option C: Google Gemini
GEMINI_API_KEY=AIza...
GEMINI_MODEL=gemini-2.5-flash

# Option D: Local Ollama
# LLM_PROVIDER=ollama
# OLLAMA_MODEL=llama3.2
```
Restart `uvicorn` — `GET /health` and the frontend `CTX` drawer will automatically show `OPENROUTER` / `OPENAI` / `GEMINI` / `OLLAMA`. If an LLM call exceeds `2.5s` or fails JSON schema validation after 1 retry, MoodBite automatically falls back to the deterministic `comfort_fast` guardrail path while keeping all dietary/allergy locks intact.

---

## Optional: PostgreSQL (`pgvector`) + Redis

```powershell
docker compose up -d
cd backend
# Set DATABASE_URL=postgresql://moodbite:moodbite_dev_password@localhost:5432/moodbite
# Set REDIS_URL=redis://localhost:6379/0
.venv\Scripts\python.exe ..\db\seed_postgres.py
```

---

## Testing & 50-Scenario Evaluation Suite

```powershell
cd backend
.venv\Scripts\pytest.exe -v
.venv\Scripts\python.exe evals\run_evals.py
```

Frontend type-check & production build:
```powershell
cd frontend
npx tsc --noEmit
npm run build
```
