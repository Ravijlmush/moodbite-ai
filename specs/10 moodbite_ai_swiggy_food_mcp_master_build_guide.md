# MoodBite AI × Swiggy Food MCP — Master Build & Integration Blueprint

> **Purpose:** Single-source-of-truth engineering specification to connect the **MoodBite AI** conversational mood-to-combo agent to **Swiggy's official Food MCP Server (`https://mcp.swiggy.com/food`)** on `localhost`, enforce strict **Black & White (`#000000` / `#FFFFFF`) UI** and safety guardrails, and prepare a production-grade 60-second demo for **Swiggy Builders Club (`builders@swiggy.in`)**.

---

## Table of Contents
1. [Product Vision & Swiggy Builders Club Alignment](#1-product-vision--swiggy-builders-club-alignment)
2. [End-to-End Architecture (Mood Agent + Swiggy MCP)](#2-end-to-end-architecture-mood-agent--swiggy-mcp)
3. [Swiggy Food MCP Integration & OAuth 2.1 Setup](#3-swiggy-food-mcp-integration--oauth-21-setup)
4. [Conversational State Machine & Prompts](#4-conversational-state-machine--prompts)
5. [Live Catalog Mood Enrichment & Combo Ranking](#5-live-catalog-mood-enrichment--combo-ranking)
6. [Monochrome Black & White UI/UX Specification](#6-monochrome-black--white-uiux-specification)
7. [API Contracts & State Persistence](#7-api-contracts--state-persistence)
8. [Non-Negotiable Rules & Safety Guardrails](#8-non-negotiable-rules--safety-guardrails)
9. [Local Build Checklist & 60-Second Demo Shot List](#9-local-build-checklist--60-second-demo-shot-list)

---

## 1. Product Vision & Swiggy Builders Club Alignment

### 1.1 The Problem
When users open Swiggy while emotionally drained, stressed after work/exams, or unwell, **decision fatigue** peaks. Scrolling dozens of restaurants and manually pairing a main dish with a drink causes browse abandonment.

### 1.2 The Solution
**MoodBite AI** is an empathetic, ultra-fast conversational food concierge built on **Swiggy Food MCP** that:
1. Conducts a natural **1-to-3 turn check-in** (never robotic, never clinical).
2. Extracts hidden emotional & situational signals (`mood`, `energy_level`, `effort_to_eat`, `craving_profile`, `max_eta_mins`).
3. Queries **real nearby restaurants and live menus** via Swiggy's MCP tools.
4. Assembles **3–5 ready-to-order meal combos** (e.g., *Homestyle Rajma Chawal Bowl + Chilled Coke*) with 1-line mood-match rationales and populates the user's real Swiggy cart in one click.

---

## 2. End-to-End Architecture (Mood Agent + Swiggy MCP)

```text
+-------------------------------------------------------------------------+
|                  MONOCHROME CLIENT UI (#000000 / #FFFFFF)               |
|  Chat Stream  |  Quick-Reply Pills  |  Combo Cards  |  Live Cart Badge  |
+------------------------------------+------------------------------------+
                                     | HTTPS / SSE
                                     v
+-------------------------------------------------------------------------+
|                 MOODBITE ORCHESTRATOR BACKEND (FastAPI)                 |
|                                                                         |
|  1. Session Store (Redis / In-Memory): Loads UserContext + Turn Count   |
|  2. LLM State Extractor (Pydantic v2 JSON): Updates Mood & Constraints  |
|  3. Decision Gate:                                                      |
|     +-- [confidence < 0.75 AND turn < 3] --> Emit 1-line Micro-Probe    |
|     +-- [confidence >= 0.75 OR turn == 3] --> Trigger MCP Combo Engine  |
+------------------------------------+------------------------------------+
                                     | Streamable HTTP + OAuth 2.1 Bearer
                                     v
+-------------------------------------------------------------------------+
|                SWIGGY FOOD MCP SERVER (mcp.swiggy.com/food)             |
|                                                                         |
|  • get_addresses          -> Resolve user delivery lat/lng & address_id |
|  • search_restaurants     -> Fetch open nearby kitchens + live ETA      |
|  • search_menu / get_menu -> Pull live dishes, beverages & prices       |
|  • update_food_cart       -> Add selected combo items directly to cart  |
|  • fetch_food_coupons     -> Surface applicable offers on the combo     |
+------------------------------------+------------------------------------+
                                     | Raw Live Menu Items
                                     v
+-------------------------------------------------------------------------+
|               REAL-TIME MOOD SCORER & COMBO ASSEMBLER                   |
|                                                                         |
|  Step A: Hard Filter (Open, ETA <= 30m, Veg/Allergy Lock, Budget)       |
|  Step B: On-the-Fly Tagging (Zero-Mess Bowls/Rolls + Sensory Match)     |
|  Step C: Same-Restaurant Main + Booster Pairing (Drink / Dessert)       |
|  Step D: Top 3–5 Diverse Combos + 1-Line LLM Rationale                  |
+-------------------------------------------------------------------------+
```

---

## 3. Swiggy Food MCP Integration & OAuth 2.1 Setup

### 3.1 Connection Details (Localhost Prototyping)
* **MCP Server Endpoint:** `https://mcp.swiggy.com/food`
* **Transport Protocol:** MCP over Streamable HTTP
* **Authentication:** OAuth 2.1 with **PKCE** (`code_challenge_method=S256`)
* **Localhost Allowance:** Swiggy Builders Club permits solo developers to authenticate and prototype on `http://localhost:<PORT>` / `http://127.0.0.1:<PORT>` with zero upfront approval.

### 3.2 Environment Variables (`.env`)
```env
# LLM Provider (Fast JSON Structured Output)
LLM_API_KEY=your_llm_api_key
LLM_MODEL=gemini-2.5-flash

# Swiggy Food MCP Configuration
SWIGGY_MCP_URL=https://mcp.swiggy.com/food
SWIGGY_OAUTH_REDIRECT_URI=http://localhost:8000/auth/swiggy/callback
DEMO_FALLBACK_MODE=false   # Set true ONLY if offline during recording backup

# Session Store
REDIS_URL=redis://localhost:6379/0
```

### 3.3 MCP Tool-to-Agent Mapping
| Agent Pipeline Stage | Swiggy Food MCP Tool | Purpose in MoodBite |
| :--- | :--- | :--- |
| **Session Init** | `get_addresses` | Retrieves saved user delivery addresses so ETA filtering is hyper-local. |
| **Candidate Discovery** | `search_restaurants` / `search_menu` | Queries craving keywords derived from mood (e.g., `"rajma chawal"`, `"khichdi"`, `"paneer roll"`, `"biryani"`). |
| **Combo Pairing** | `get_restaurant_menu` (or menu payload) | Fetches beverages (`Coke`, `Chaas`, `Lemonade`) & desserts (`Gulab Jamun`) from the **exact same restaurant** to keep single-order ETA low. |
| **One-Tap Conversion** | `update_food_cart` | Adds both `main_item_id` and `booster_item_id` directly into the user's live Swiggy cart when `+ ADD COMBO TO CART` is clicked. |
| **Value Booster (Optional)** | `fetch_food_coupons` | Checks if an instant coupon applies to the combo subtotal. |

### 3.4 Python MCP Client Wrapper Skeleton (`mcp_client.py`)
```python
import httpx
from typing import Any, Dict, List

class SwiggyFoodMCPClient:
    def __init__(self, access_token: str, mcp_url: str = "https://mcp.swiggy.com/food"):
        self.mcp_url = mcp_url
        self.headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
        }

    async def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        payload = {
            "jsonrpc": "2.0",
            "id": f"moodbite_{tool_name}",
            "method": "tools/call",
            "params": {
                "name": tool_name,
                "arguments": arguments,
            },
        }
        async with httpx.AsyncClient(timeout=8.0) as client:
            resp = await client.post(self.mcp_url, json=payload, headers=self.headers)
            resp.raise_for_status()
            return resp.json()

    async def search_craving_dishes(self, query: str, address_id: str) -> List[Dict[str, Any]]:
        result = await self.call_tool("search_menu", {"query": query, "address_id": address_id})
        return result.get("result", {}).get("content", [])

    async def add_combo_to_cart(self, restaurant_id: str, item_ids: List[str], address_id: str) -> Dict[str, Any]:
        items_payload = [{"item_id": iid, "quantity": 1} for iid in item_ids]
        return await self.call_tool(
            "update_food_cart",
            {"restaurant_id": restaurant_id, "items": items_payload, "address_id": address_id},
        )
```

---

## 4. Conversational State Machine & Prompts

### 4.1 `UserContext` Schema (Pydantic v2)
```json
{
  "session_id": "sess_98a7f1",
  "turn_count": 1,
  "user_state": {
    "primary_mood": "tired_and_down",
    "emotional_valence": -0.6,
    "energy_level": "low",
    "goal": "comfort_and_cheer_up"
  },
  "food_preferences": {
    "craving_profiles": ["warm_comfort", "nostalgic", "fizzy_sweet_kick"],
    "search_queries": ["rajma chawal", "dal khichdi", "paneer roll"],
    "effort_to_eat": "zero_mess",
    "spice_tolerance": "medium"
  },
  "hard_constraints": {
    "dietary_type": "veg",
    "allergies": [],
    "max_budget_inr": 350,
    "max_eta_mins": 30
  },
  "routing": {
    "state_confidence": 0.89,
    "next_action": "recommend_combos",
    "clarifying_question": null
  }
}
```

### 4.2 Master System Prompt
```text
You are MoodBite, an empathetic, street-smart food concierge connected to Swiggy.
Your job is to understand how the user is feeling and what kind of day they are having in 1 to 3 brief, natural turns, and then trigger a curated list of 3-5 fast-arriving meal combos.

CORE PERSONALITY:
- Sound like a perceptive, supportive friend—warm, casual, concise, never robotic.
- NEVER sound like a therapist, doctor, or nutritionist. Never diagnose emotions or lecture about healthy eating.
- Keep every reply under 40 words before recommendations appear.

CONVERSATION RULES:
1. TURN 1 (Warm Check-In): If the user opens vaguely ("hi", "hungry", "what should I eat?"), ask a casual vibe check ("Hey! Rough day, chill evening, or celebrating something? Tell me the vibe.") and emit 3-4 quick-reply pills.
2. TURN 2 (Micro-Probe): If mood is known ("tired", "stressed") but flavor direction isn't, validate in 1 short sentence and ask ONE crisp question ("Warm comfort food or something spicy/crunchy to wake your brain up?").
3. TURN 3 CEILING: By Turn 3 at the latest (or Turn 1/2 if mood + craving are clear, e.g., "super tired and mood is off, want something fast that cheers me up"), set `next_action = "recommend_combos"`.
4. TIRED / LOW-ENERGY RULE: Whenever `energy_level == "low"`, automatically set `effort_to_eat = "zero_mess"` (prioritize bowls, rolls, biryani, wraps) and `max_eta_mins = 30`.
5. MCP SEARCH QUERIES: Populate `food_preferences.search_queries` with 2-3 specific Indian delivery dish keywords matching the mood (e.g., ["rajma chawal bowl", "dal khichdi", "paneer tikka roll"]).
6. DIETARY PERSISTENCE: Never drop `dietary_type` or `allergies` set in earlier turns.

OUTPUT FORMAT (STRICT JSON):
{
  "updated_context": { ...UserContext... },
  "reply_text": "string",
  "quick_reply_pills": ["string", "string", "string"]
}
```

---

## 5. Live Catalog Mood Enrichment & Combo Ranking

Because live Swiggy MCP search results return raw restaurant and menu metadata (`name`, `price`, `is_veg`, `rating`, `sla_mins`), MoodBite applies a **fast in-memory heuristic + embedding scorer** in `< 80 ms`:

### 5.1 Mood-to-Combo Archetype Matrix
| User Mood / State | Target Main Archetype (`search_queries`) | Booster Pairing Rule (Same Restaurant) | Example Live Combo |
| :--- | :--- | :--- | :--- |
| `tired_and_down` | Warm nostalgic bowls (`rajma chawal`, `dal khichdi`, `biryani`) | Cold fizzy drink (`Coke`, `Thums Up`, `Limca`) OR warm sweet (`Gulab Jamun`) | **Homestyle Rajma Chawal Bowl + Chilled Coke** |
| `stressed_anxious` | High-texture spicy/crunchy (`paneer tikka roll`, `chilli garlic noodles`, `momos`) | Cooling palate balancer (`Masala Chaas`, `Mint Lemonade`) | **Smoky Paneer Roll + Masala Lemonade** |
| `sluggish_heavy` | Light, gut-friendly (`curd rice`, `clear soup`, `idli`, `poha`) | Digestive/citrus drink (`Fresh Lime Soda`, `Ginger Lemon Tea`) | **Tadka Curd Rice + Fresh Lime Soda** |
| `celebrating_happy` | Indulgent treat (`butter chicken bowl`, `loaded burger`, `pizza`) | Signature dessert (`Choco Lava Cake`, `Brownie`) | **Paneer Makhani Bowl + Choco Lava Cake** |

### 5.2 Multi-Objective Combo Scoring Formula
For each candidate pair $c = (\text{main}, \text{booster})$ from the same restaurant:

$$\text{Score}(c) = 0.40 \cdot S_{\text{mood}}(c) + 0.25 \cdot S_{\text{eta}}(c) + 0.15 \cdot S_{\text{effort}}(c) + 0.10 \cdot S_{\text{rating}}(c) + 0.10 \cdot S_{\text{affinity}}(c)$$

* **$S_{\text{mood}}(c) \in [0, 1]$:** Keyword + semantic similarity between `craving_profiles` and dish title/description.
* **$S_{\text{eta}}(c) = \max\left(0, 1 - \frac{\text{sla\_mins}}{45}\right)$:** Heavily rewards sub-25-minute delivery.
* **$S_{\text{effort}}(c)$:** `1.0` if dish matches `zero_mess` keywords (`bowl`, `roll`, `wrap`, `biryani`, `khichdi`, `rice`) when `energy_level == "low"`; `0.5` otherwise.
* **$S_{\text{rating}}(c) = \text{clamp}\left(\frac{\text{rating} - 3.0}{2.0}, 0, 1\right)$**.
* **$S_{\text{affinity}}(c)$:** `1.0` if a valid beverage/dessert from the same restaurant is paired; `0.4` if standalone main.

**Diversity Rule:** Return **3 to 5 combos**, enforcing **maximum 1 combo per restaurant** so the user gets distinct options.

---

## 6. Monochrome Black & White UI/UX Specification

### 6.1 Strict Palette & CSS Variables
Zero brand colors, zero gradients, zero drop shadows. Contrast is driven purely by `#000000` and `#FFFFFF`.

```css
:root {
  --bg-primary: #FFFFFF;
  --bg-inverse: #000000;
  --bg-subtle: #F7F7F7;
  --text-primary: #000000;
  --text-secondary: #525252;
  --text-inverse: #FFFFFF;
  --border-hairline: 1px solid #E5E5E5;
  --border-strong: 1.5px solid #000000;
  --radius-card: 12px;
  --radius-pill: 9999px;
}
```

### 6.2 Mobile-First Wireframe (390px Viewport)
```text
+--------------------------------------------------+
| <-  MOODBITE × SWIGGY MCP        [VEG] [CART: 0] |  <- 1.5px #000 bottom border
+--------------------------------------------------+
|                                                  |
|  MOODBITE                                        |
|  +--------------------------------------------+  |
|  | Hey! Rough day, chill evening, or just     |  |  <- #FFF bubble, 1px #000 border
|  | need fast food so you don't have to think? |  |
|  +--------------------------------------------+  |
|                                                  |
|              +--------------------------------+  |
|              | super tired and mood is off,   |  |  <- Solid #000 bubble, #FFF text
|              | want something fast to cheer up|  |
|              +--------------------------------+  |
|                                                  |
|  [DEBUG PILL: MOOD=TIRED_DOWN | EFFORT=ZERO-MESS]|  <- Optional toggle for demo video
|                                                  |
|  MOODBITE                                        |
|  Say no more—zero-mess comfort coming right up:  |
|                                                  |
|  +--------------------------------------------+  |
|  | [COMFORT CLASSIC]           22 MINS • ₹219 |  |  <- Inverted #000 badge
|  | Homestyle Rajma Chawal + Chilled Coke      |  |
|  | Punjabi Angithi • ★ 4.4                    |  |
|  | Warm, zero-effort bowl with a cold fizzy   |  |
|  | kick to lift your mood fast.               |  |
|  |                                            |  |
|  | [ + ADD COMBO TO SWIGGY CART ]             |  |  <- Full-width #000 button
|  +--------------------------------------------+  |
|                                                  |
|  REFINE LIST:                                    |
|  ( Under ₹250 )  ( Spicier )  ( Swap Drink )     |  <- 1px #000 outline pills
+--------------------------------------------------+
|  Type how you're feeling...              [ -> ]  |  <- 1.5px #000 input bar
+--------------------------------------------------+
```

---

## 7. API Contracts & State Persistence

### 7.1 `POST /api/v1/chat/turn`
**Request:**
```json
{
  "session_id": "sess_98a7f1",
  "message": "super tired and mood is kinda off, want something fast that cheers me up",
  "swiggy_access_token": "eyJhbGciOi...",
  "address_id": "addr_9921",
  "active_filters": {
    "dietary_type": "veg",
    "max_budget_inr": null
  }
}
```

**Response:**
```json
{
  "session_id": "sess_98a7f1",
  "turn_count": 1,
  "action": "recommend_combos",
  "agent_message": "Say no more—no-mess comfort food coming right up. Here are 3 fast Swiggy combos near you built to lift a tired mood:",
  "user_context": {
    "primary_mood": "tired_and_down",
    "energy_level": "low",
    "effort_to_eat": "zero_mess",
    "max_eta_mins": 30
  },
  "recommendations": [
    {
      "combo_id": "cmb_882_10492_201",
      "mood_badge": "COMFORT CLASSIC",
      "title": "Homestyle Rajma Chawal Bowl + Chilled Coke (300ml)",
      "restaurant": {
        "id": "rest_882",
        "name": "Punjabi Angithi",
        "rating": 4.4,
        "eta_mins": 22
      },
      "items": [
        { "item_id": "10492", "name": "Homestyle Rajma Chawal Bowl", "price_inr": 179 },
        { "item_id": "201", "name": "Coca-Cola Can (300ml)", "price_inr": 40 }
      ],
      "total_price_inr": 219,
      "why_it_fits": "Warm, zero-effort bowl with a cold fizzy kick to lift your mood fast.",
      "match_score": 0.94
    }
  ],
  "quick_reply_pills": ["Under ₹250", "Make it spicier", "Something lighter", "Swap drink"]
}
```

### 7.2 `POST /api/v1/cart/add-combo`
Calls `SwiggyFoodMCPClient.add_combo_to_cart(restaurant_id, item_ids, address_id)` and returns live cart confirmation + updated cart count for the UI header.

---

## 8. Non-Negotiable Rules & Safety Guardrails

1. **The 3-Turn Ceiling Rule:** Never ask more than 2 follow-up questions. By Turn 3 at the latest, always output `action = "recommend_combos"` with `>= 3` combos.
2. **Zero-Hallucination Catalog Rule:** Every dish name, price, restaurant ID, and ETA shown in the UI MUST originate from live Swiggy Food MCP responses (or verified fallback fixtures when `DEMO_FALLBACK_MODE=true`).
3. **Immutable Dietary & Allergy Lock:** Once `veg`, `vegan`, `jain`, or an allergy is stated or toggled in the UI header, enforce it deterministically across every MCP search and combo assembly step.
4. **Medical & Mental Health Boundary:** MoodBite is a culinary concierge, never a medical/mental health advisor. Never diagnose conditions or lecture users about sugar/calories. If severe crisis/self-harm language is detected, bypass food recommendations and show helpline numbers.
5. **Strict Monochrome UI Enforcement:** Only `#000000`, `#FFFFFF`, and neutral grayscale steps (`#121212`, `#525252`, `#E5E5E5`, `#F7F7F7`) are allowed. No colored stars, green/red veg dots (use bordered `[VEG]` / `[NON-VEG]` monochrome tags), or drop shadows.
6. **Latency Fallback:** If Swiggy MCP or LLM extraction exceeds `3.0s`, gracefully retry once or serve cached nearby combos so the user never hits a dead screen.

---

## 9. Local Build Checklist & 60-Second Demo Shot List

### 9.1 Pre-Recording Checklist
- [ ] Start FastAPI backend on `http://localhost:8000` and Next.js monochrome UI on `http://localhost:3000`.
- [ ] Complete OAuth 2.1 + PKCE login against `https://mcp.swiggy.com/food` so `get_addresses` and `search_menu` return real nearby restaurants.
- [ ] Verify `[VEG]` toggle and `[CART: 0]` counter work cleanly in the top monochrome header.
- [ ] Enable the subtle `[STATE INSPECTOR]` pill in the UI so reviewers at `builders@swiggy.in` can see `UserContext` JSON updating live.

### 9.2 60-Second Demo Video Shot List (For `builders@swiggy.in`)
1. **`0:00 – 0:10` (The Problem):** Show the clean B&W MoodBite chat screen. Voiceover: *"Decision fatigue hits hardest when you're exhausted. MoodBite turns a 2-turn chat into fast, mood-matched Swiggy combos."*
2. **`0:10 – 0:25` (Vibe Check & State Extraction):** Type *"super tired and mood is kinda off, want something fast that cheers me up"*. Show `UserContext` resolving `primary_mood: tired_and_down`, `effort_to_eat: zero_mess`, `max_eta_mins: 30`.
3. **`0:25 – 0:45` (Live Swiggy MCP Combos & Refinement):** Show real nearby restaurants + paired combos (*Rajma Chawal Bowl + Chilled Coke*), then tap `( Under ₹250 )` to demonstrate instant re-ranking.
4. **`0:45 – 0:60` (One-Tap Swiggy Cart Population):** Click `[ + ADD COMBO TO SWIGGY CART ]`, show `[CART: 2]` updating via Swiggy's `update_food_cart` MCP tool, and conclude with the architecture overlay (`FastAPI + Swiggy Food MCP`).