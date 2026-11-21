# 04 — Recommendation & Combo Ranking Engine

## 1. Offline Menu Enrichment Schema
Standard Zomato/delivery catalogs only contain dish names, prices, and cuisine tags. An offline batch job enriches each menu item with mood and consumption metadata:

```json
{
  "item_id": "dish_10492",
  "restaurant_id": "rest_882",
  "name": "Homestyle Rajma Chawal Bowl",
  "category": "main_bowl",
  "dietary_type": "veg",
  "allergens": ["dairy"],
  "price_inr": 179,
  "prep_time_mins": 12,
  "mood_tags": ["comfort_classic", "nostalgic", "grounding", "cheer_up"],
  "sensory_tags": ["warm", "hearty", "mildly_spiced", "soft"],
  "effort_to_eat": "zero_mess",
  "dopamine_score": 0.86,
  "heavy_index": 0.65,
  "pairing_affinities": ["beverage_coke_can", "beverage_masala_chaas", "dessert_gulab_jamun"],
  "embedding_vector": [0.012, -0.044, "..."]
}
```

## 2. Dynamic Combo Assembly Rules
Users in a low mood respond far better to a complete meal combo than a standalone dish. The engine dynamically pairs a **Main** + **Booster (Beverage or Dessert)** from the **same restaurant**:

| User Mood / State | Main Dish Archetype | Booster Pairing Rule | Example Combo |
| :--- | :--- | :--- | :--- |
| `tired_and_down` | Warm nostalgic bowl (`rajma_chawal`, `dal_khichdi`, `biryani`) | Cold fizzy drink (`Coke`, `Limca`) OR warm sweet (`Gulab Jamun`) | **Rajma Chawal Bowl + Chilled Coke** |
| `stressed_angry` | High-texture spicy/crunchy (`paneer_tikka_roll`, `chilli_garlic_noodles`) | Cooling palate balancer (`Masala Chaas`, `Mint Lemonade`) | **Smoky Paneer Roll + Masala Lemonade** |
| `sluggish_heavy` | Light, gut-friendly (`curd_rice`, `clear_soup_bowl`, `poha`) | Digestive/citrus drink (`Ginger Lemon Tea`, `Fresh Lime Soda`) | **Tadka Curd Rice + Fresh Lime Soda** |
| `celebratory_happy` | Indulgent treat (`loaded_burger`, `butter_chicken_bowl`, `pizza`) | Dessert or shake (`Choco Lava Cake`, `Cold Coffee`) | **Paneer Makhani Bowl + Choco Lava Cake** |

## 3. Four-Stage Retrieval & Ranking Pipeline

### Stage 1: Hard Safety & Logistics Filter (SQL)
Discard any restaurant or dish failing:
- `restaurant.is_open == True` AND `live_eta_mins <= user_context.hard_constraints.max_eta_mins`
- `dish.dietary_type` matches user constraint (`veg` excludes `non_veg` and `egg`).
- `dish.allergens` has zero intersection with `user_context.hard_constraints.allergies`.
- `(main.price_inr + booster.price_inr) <= user_context.hard_constraints.max_budget_inr`.

### Stage 2: Semantic + Tag Retrieval
Compute cosine similarity between `user_state` query embedding and `dish.embedding_vector`, boosted by exact overlap on `mood_tags` and `effort_to_eat`. Retrieve top `K = 25` candidate mains.

### Stage 3: Multi-Factor Scoring Formula
For each candidate combo $c = (	ext{main}, 	ext{booster})$:

$$	ext{Score}(c) = 0.40 \cdot S_{	ext{mood}}(c) + 0.25 \cdot S_{	ext{eta}}(c) + 0.15 \cdot S_{	ext{effort}}(c) + 0.10 \cdot S_{	ext{rating}}(c) + 0.10 \cdot S_{	ext{affinity}}(c)$$

Where:
- $S_{	ext{mood}}(c) \in [0,1]$: Cosine similarity + tag intersection between `craving_profiles` and combo tags.
- $S_{	ext{eta}}(c) = \max\left(0, 1 - rac{	ext{live\_eta\_mins}}{45}ight)$: Strongly rewards sub-25-minute delivery.
- $S_{	ext{effort}}(c)$: `1.0` if `effort_to_eat == "zero_mess"` when user energy is `low`; `0.5` otherwise.
- $S_{	ext{rating}}(c) = rac{	ext{restaurant.rating} - 3.0}{2.0}$ (clamped to `[0, 1]`).
- $S_{	ext{affinity}}(c)$: `1.0` if `booster.id` is in `main.pairing_affinities`.

### Stage 4: Diversity & Deduplication
Return top **3 to 5 combos**, enforcing a maximum of **1 combo per restaurant** and distinct main-dish archetypes (e.g., 1 rice bowl, 1 roll/wrap, 1 khichdi/noodle option) so the list feels curated rather than repetitive.
