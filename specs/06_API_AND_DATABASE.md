# 06 — API Contracts & Database Schema

## 1. REST / SSE Endpoints

### `POST /api/v1/chat/turn`
Processes a user message or quick-reply pill tap, updates `UserContext`, and returns either a conversational follow-up or a ranked list of meal combos.

**Request Payload:**
```json
{
  "session_id": "sess_98a7f1",
  "user_id": "usr_4412",
  "message": "super tired and mood is kinda off, want something fast that cheers me up",
  "location": {
    "lat": 28.6139,
    "lng": 77.2090
  },
  "active_filters": {
    "dietary_type": "veg",
    "max_budget_inr": null
  }
}
```

**Response Payload (`200 OK`):**
```json
{
  "session_id": "sess_98a7f1",
  "turn_count": 1,
  "action": "recommend_combos",
  "agent_message": "Say no more—no-mess comfort food coming right up. Here are 3 fast combos near you built to lift a tired mood:",
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
        { "item_id": "dish_10492", "name": "Homestyle Rajma Chawal Bowl", "price_inr": 179 },
        { "item_id": "bev_201", "name": "Coca-Cola Can (300ml)", "price_inr": 40 }
      ],
      "total_price_inr": 219,
      "why_it_fits": "Warm, zero-effort bowl with a cold fizzy kick to lift your mood fast.",
      "match_score": 0.94
    }
  ],
  "quick_reply_pills": [
    "Under ₹250",
    "Make it spicier",
    "Something lighter",
    "Swap drink"
  ]
}
```

### `POST /api/v1/chat/refine`
Applies one-tap refinement chips (`"Under ₹250"`, `"Swap drink"`, `"Lighter"`) directly to the existing `UserContext` without re-running mood extraction from scratch.

## 2. PostgreSQL + `pgvector` Schema
```sql
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE restaurants (
    id VARCHAR(32) PRIMARY KEY,
    name VARCHAR(120) NOT NULL,
    rating NUMERIC(2,1) NOT NULL,
    lat DOUBLE PRECISION NOT NULL,
    lng DOUBLE PRECISION NOT NULL,
    base_prep_mins INT NOT NULL,
    is_open BOOLEAN DEFAULT TRUE
);

CREATE TABLE menu_items (
    id VARCHAR(32) PRIMARY KEY,
    restaurant_id VARCHAR(32) REFERENCES restaurants(id),
    name VARCHAR(160) NOT NULL,
    category VARCHAR(32) NOT NULL, -- 'main_bowl', 'roll_wrap', 'beverage', 'dessert'
    dietary_type VARCHAR(16) NOT NULL, -- 'veg', 'egg', 'non_veg'
    allergens TEXT[] DEFAULT '{}',
    price_inr INT NOT NULL,
    mood_tags TEXT[] NOT NULL,
    sensory_tags TEXT[] NOT NULL,
    effort_to_eat VARCHAR(24) NOT NULL, -- 'zero_mess', 'standard'
    pairing_affinities TEXT[] DEFAULT '{}',
    mood_embedding vector(384),
    is_available BOOLEAN DEFAULT TRUE
);

CREATE INDEX idx_menu_mood_embedding ON menu_items USING ivfflat (mood_embedding vector_cosine_ops) WITH (lists = 100);
CREATE INDEX idx_menu_dietary ON menu_items (dietary_type, is_available);
```
