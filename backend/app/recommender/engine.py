"""Deterministic 4-Stage Recommendation & Combo Ranking Engine (Spec 04)."""

from __future__ import annotations

from dataclasses import dataclass

from app.agent.nlg import build_mood_badge, build_why_it_fits
from app.recommender.catalog_repo import CatalogRepository, compute_live_eta_mins
from app.recommender.embeddings import EmbeddingService, cosine_similarity
from app.schemas.api import Location
from app.schemas.catalog import ComboItem, ComboRecommendation, ComboRestaurant, MenuItem, Restaurant
from app.schemas.context import DietaryType, UserContext

BOOSTER_CATEGORIES = {"beverage", "dessert"}

# Mood -> preferred booster sensory/mood keywords (Spec 04 Dynamic Combo Assembly Rules)
MOOD_BOOSTER_AFFINITY: dict[str, set[str]] = {
    "tired_and_down": {"fizzy_sweet_kick", "fizzy", "sweet_treat", "caffeine", "warm"},
    "stressed_angry": {"cooling", "citrus", "minty", "digestive", "light"},
    "sluggish_heavy": {"digestive", "citrus", "light_comfort", "soothing", "herbal"},
    "celebratory_happy": {"sweet_treat", "celebratory_happy", "rich", "creamy", "fizzy_sweet_kick"},
    "heartbroken_low": {"sweet_treat", "warm", "nostalgic", "creamy", "rich"},
    "bored_restless": {"fizzy_sweet_kick", "tangy", "citrus", "sweet_treat"},
}

ALLERGY_SYNONYMS: dict[str, tuple[str, ...]] = {
    "dairy": ("dairy", "milk", "paneer", "cheese", "butter", "ghee", "creamy", "curd", "lassi", "chaas", "makhani", "kheer", "gulab jamun"),
    "peanuts": ("peanuts", "peanut"),
    "nuts": ("nuts", "nut", "almond", "badam", "cashew", "pistachio", "pista", "walnut", "peanuts"),
    "gluten": ("gluten", "wheat", "naan", "roti", "paratha", "kulcha", "roll", "wrap", "noodles", "pasta", "mac", "brownie", "cookie", "cake", "croutons", "toastie", "pav"),
    "egg": ("egg", "eggs", "omelette", "custard"),
    "soy": ("soy", "soya", "tofu", "teriyaki", "manchurian", "hakka", "schezwan"),
    "sesame": ("sesame", "tahini", "hummus"),
}


def item_matches_dietary(item: MenuItem, dietary_type: DietaryType | None) -> bool:
    if not dietary_type or dietary_type == "any" or dietary_type == "non_veg":
        return True
    if dietary_type == "veg":
        return item.dietary_type == "veg"
    if dietary_type == "eggetarian":
        return item.dietary_type in ("veg", "egg")
    if dietary_type == "jain":
        return item.dietary_type == "veg" and "jain" in item.dietary_tags
    if dietary_type == "vegan":
        return (
            item.dietary_type == "veg"
            and "vegan" in item.dietary_tags
            and "dairy" not in item.allergens
            and "egg" not in item.allergens
        )
    if dietary_type == "halal":
        return item.dietary_type == "veg" or "halal" in item.dietary_tags
    return True


def item_is_allergy_safe(
    item: MenuItem,
    allergies: list[str],
    excluded_ingredients: list[str],
) -> bool:
    lowered_name = item.name.lower()
    item_allergens = {a.lower() for a in item.allergens}

    for allergy in allergies:
        a_norm = allergy.strip().lower()
        if not a_norm:
            continue
        if a_norm in item_allergens:
            return False
        if a_norm == "nuts" and ("peanuts" in item_allergens or "nuts" in item_allergens):
            return False
        synonyms = ALLERGY_SYNONYMS.get(a_norm, (a_norm,))
        for syn in synonyms:
            # Explicit allergen tag match always fails; name match checks ingredient tokens
            if syn in item_allergens:
                return False
            if syn == "dairy" and "vegan" in item.dietary_tags:
                continue
            if syn in lowered_name and a_norm not in ("dairy", "gluten"):
                return False

    for excluded in excluded_ingredients:
        ex_norm = excluded.strip().lower()
        if ex_norm and ex_norm in lowered_name:
            return False

    return True


@dataclass
class _ScoredCombo:
    main: MenuItem
    booster: MenuItem
    restaurant: Restaurant
    eta_mins: int
    total_score: float
    mood_score: float


class RecommendationEngine:
    """Four-stage hybrid retrieval and deterministic combo ranking engine."""

    def __init__(self, catalog: CatalogRepository, embedder: EmbeddingService | None = None) -> None:
        self.catalog = catalog
        self.embedder = embedder or EmbeddingService()

    def recommend(
        self,
        context: UserContext,
        location: Location,
        user_message: str = "",
        limit: int = 4,
        swap_drink_step: int = 0,
    ) -> list[ComboRecommendation]:
        limit = max(3, min(5, limit))
        query_vec = self.embedder.embed_user_context(context, user_message=user_message)

        # Stage 1: Hard Safety & Logistics Filter
        open_restaurants: dict[str, tuple[Restaurant, int]] = {}
        for rest in self.catalog.list_restaurants():
            if not rest.is_open:
                continue
            eta = compute_live_eta_mins(rest, location)
            if eta <= context.hard_constraints.max_eta_mins:
                open_restaurants[rest.id] = (rest, eta)

        dietary = context.hard_constraints.dietary_type
        allergies = context.hard_constraints.allergies
        excluded = context.food_preferences.excluded_ingredients
        budget = context.hard_constraints.max_budget_inr

        mains_by_rest: dict[str, list[MenuItem]] = {}
        boosters_by_rest: dict[str, list[MenuItem]] = {}

        for item in self.catalog.list_items():
            if not item.is_available:
                continue
            if item.restaurant_id not in open_restaurants:
                continue
            if not item_matches_dietary(item, dietary):
                continue
            if not item_is_allergy_safe(item, allergies, excluded):
                continue

            if item.category in BOOSTER_CATEGORIES:
                boosters_by_rest.setdefault(item.restaurant_id, []).append(item)
            else:
                mains_by_rest.setdefault(item.restaurant_id, []).append(item)

        # Stage 2: Semantic + Tag Retrieval (Top K = 25 candidate mains)
        candidate_mains: list[tuple[MenuItem, float]] = []
        for rest_id, rest_mains in mains_by_rest.items():
            if not boosters_by_rest.get(rest_id):
                continue
            for main in rest_mains:
                s_mood = self._compute_mood_score(main, context, query_vec)
                candidate_mains.append((main, s_mood))

        candidate_mains.sort(key=lambda pair: pair[1], reverse=True)
        top_k_mains = candidate_mains[:25]

        # Stage 3: Same-Restaurant Combo Assembly & Multi-Factor Scoring
        scored_combos: list[_ScoredCombo] = []
        for main, main_mood_score in top_k_mains:
            rest, eta = open_restaurants[main.restaurant_id]
            eligible_boosters = boosters_by_rest.get(main.restaurant_id, [])
            if budget is not None:
                eligible_boosters = [b for b in eligible_boosters if (main.price_inr + b.price_inr) <= budget]
            if not eligible_boosters:
                continue

            ranked_boosters = self._rank_boosters(main, eligible_boosters, context)
            chosen_booster, affinity_score = ranked_boosters[swap_drink_step % len(ranked_boosters)]

            total_score = self._compute_combo_score(
                main=main,
                booster=chosen_booster,
                restaurant=rest,
                eta_mins=eta,
                main_mood_score=main_mood_score,
                affinity_score=affinity_score,
                context=context,
            )
            scored_combos.append(
                _ScoredCombo(
                    main=main,
                    booster=chosen_booster,
                    restaurant=rest,
                    eta_mins=eta,
                    total_score=total_score,
                    mood_score=main_mood_score,
                )
            )

        # If top-25 mains didn't yield 3 distinct restaurants under tight budget, scan remaining mains safely
        distinct_rest_count = len({c.restaurant.id for c in scored_combos})
        if distinct_rest_count < 3 and len(candidate_mains) > 25:
            for main, main_mood_score in candidate_mains[25:]:
                rest, eta = open_restaurants[main.restaurant_id]
                eligible_boosters = boosters_by_rest.get(main.restaurant_id, [])
                if budget is not None:
                    eligible_boosters = [b for b in eligible_boosters if (main.price_inr + b.price_inr) <= budget]
                if not eligible_boosters:
                    continue
                ranked_boosters = self._rank_boosters(main, eligible_boosters, context)
                chosen_booster, affinity_score = ranked_boosters[swap_drink_step % len(ranked_boosters)]
                total_score = self._compute_combo_score(
                    main=main,
                    booster=chosen_booster,
                    restaurant=rest,
                    eta_mins=eta,
                    main_mood_score=main_mood_score,
                    affinity_score=affinity_score,
                    context=context,
                )
                scored_combos.append(
                    _ScoredCombo(
                        main=main,
                        booster=chosen_booster,
                        restaurant=rest,
                        eta_mins=eta,
                        total_score=total_score,
                        mood_score=main_mood_score,
                    )
                )

        # Stage 4: Diversity & Restaurant Deduplication (max 1 combo per restaurant, distinct archetypes)
        selected = self._select_diverse_combos(scored_combos, limit=limit)
        return [self._to_recommendation(combo, context) for combo in selected]

    def _compute_mood_score(self, main: MenuItem, context: UserContext, query_vec: list[float]) -> float:
        item_vec = self.catalog.get_item_embedding(main.id)
        cos_sim = cosine_similarity(query_vec, item_vec)

        desired_tokens = {
            context.user_state.primary_mood.lower(),
            context.user_state.goal.lower(),
            *context.food_preferences.craving_profiles,
        }
        item_tokens = {t.lower() for t in (*main.mood_tags, *main.sensory_tags)}
        overlap = len(desired_tokens & item_tokens)
        tag_score = min(1.0, overlap / max(1, min(len(desired_tokens), 4)))

        # Spice & heaviness modulation
        modifier = 0.0
        if context.food_preferences.spice_tolerance == "high" and any(
            t in item_tokens for t in ("spicy", "fiery", "bold_spicy", "smoky")
        ):
            modifier += 0.14
        elif context.food_preferences.spice_tolerance == "mild" and main.heavy_index <= 0.45:
            modifier += 0.10

        if "light_comfort" in desired_tokens or context.user_state.primary_mood == "sluggish_heavy":
            modifier += 0.15 if main.heavy_index <= 0.38 else -0.10

        if "sweet_treat" in desired_tokens or context.user_state.primary_mood == "celebratory_happy":
            modifier += 0.08 * main.dopamine_score

        if context.hard_constraints.max_budget_inr and context.hard_constraints.max_budget_inr <= 220:
            if "budget_friendly" in item_tokens or main.price_inr <= 155:
                modifier += 0.08

        raw = 0.55 * cos_sim + 0.35 * tag_score + 0.10 * main.dopamine_score + modifier
        return max(0.0, min(1.0, raw))

    def _rank_boosters(
        self,
        main: MenuItem,
        boosters: list[MenuItem],
        context: UserContext,
    ) -> list[tuple[MenuItem, float]]:
        desired_booster_tags = set(MOOD_BOOSTER_AFFINITY.get(context.user_state.primary_mood, set()))
        if "sweet_treat" in context.food_preferences.craving_profiles:
            desired_booster_tags.update({"sweet_treat", "warm", "fudgy"})
        if "fizzy_sweet_kick" in context.food_preferences.craving_profiles:
            desired_booster_tags.update({"fizzy_sweet_kick", "fizzy"})
        if "light_comfort" in context.food_preferences.craving_profiles:
            desired_booster_tags.update({"digestive", "light_comfort", "cooling", "citrus"})

        ranked: list[tuple[MenuItem, float, float]] = []
        for booster in boosters:
            in_affinity = booster.id in main.pairing_affinities
            b_tags = {t.lower() for t in (*booster.mood_tags, *booster.sensory_tags)}
            mood_fit = len(desired_booster_tags & b_tags)
            affinity_score = 1.0 if in_affinity else (0.55 if mood_fit > 0 else 0.2)
            tie_score = affinity_score + 0.12 * mood_fit + (0.05 if booster.category == "beverage" else 0.02)
            ranked.append((booster, affinity_score, tie_score))

        ranked.sort(key=lambda x: x[2], reverse=True)
        return [(b, aff) for b, aff, _ in ranked]

    def _compute_combo_score(
        self,
        *,
        main: MenuItem,
        booster: MenuItem,
        restaurant: Restaurant,
        eta_mins: int,
        main_mood_score: float,
        affinity_score: float,
        context: UserContext,
    ) -> float:
        # Spec 04 Stage 3 exact multi-factor formula:
        # Score(c) = 0.40 * S_mood + 0.25 * S_eta + 0.15 * S_effort + 0.10 * S_rating + 0.10 * S_affinity
        s_mood = main_mood_score
        s_eta = max(0.0, min(1.0, 1.0 - (eta_mins / 45.0)))

        if context.user_state.energy_level == "low" or context.food_preferences.effort_to_eat == "zero_mess":
            s_effort = 1.0 if main.effort_to_eat == "zero_mess" else 0.5
        else:
            s_effort = 0.85 if main.effort_to_eat == "zero_mess" else 0.75

        s_rating = max(0.0, min(1.0, (restaurant.rating - 3.0) / 2.0))
        s_affinity = affinity_score

        score = (
            0.40 * s_mood
            + 0.25 * s_eta
            + 0.15 * s_effort
            + 0.10 * s_rating
            + 0.10 * s_affinity
        )
        return round(max(0.0, min(1.0, score)), 4)

    def _select_diverse_combos(self, scored: list[_ScoredCombo], limit: int) -> list[_ScoredCombo]:
        scored.sort(key=lambda c: c.total_score, reverse=True)
        chosen: list[_ScoredCombo] = []
        used_restaurants: set[str] = set()
        used_categories: set[str] = set()

        # Pass 1: maximize both restaurant uniqueness and main-dish archetype diversity
        for combo in scored:
            if combo.restaurant.id in used_restaurants:
                continue
            if combo.main.category in used_categories:
                continue
            chosen.append(combo)
            used_restaurants.add(combo.restaurant.id)
            used_categories.add(combo.main.category)
            if len(chosen) >= limit:
                return chosen

        # Pass 2: fill up to limit while strictly enforcing max 1 combo per restaurant
        for combo in scored:
            if combo.restaurant.id in used_restaurants:
                continue
            chosen.append(combo)
            used_restaurants.add(combo.restaurant.id)
            if len(chosen) >= limit:
                break

        return chosen

    def _to_recommendation(self, combo: _ScoredCombo, context: UserContext) -> ComboRecommendation:
        total_price = combo.main.price_inr + combo.booster.price_inr
        # Overall combo dietary classification (veg only if both items are veg)
        if combo.main.dietary_type == "non_veg" or combo.booster.dietary_type == "non_veg":
            combo_diet = "non_veg"
        elif combo.main.dietary_type == "egg" or combo.booster.dietary_type == "egg":
            combo_diet = "egg"
        else:
            combo_diet = "veg"

        return ComboRecommendation(
            combo_id=f"cmb_{combo.restaurant.id}_{combo.main.id}_{combo.booster.id}",
            mood_badge=build_mood_badge(combo.main, context),
            title=f"{combo.main.name} + {combo.booster.name}",
            restaurant=ComboRestaurant(
                id=combo.restaurant.id,
                name=combo.restaurant.name,
                rating=combo.restaurant.rating,
                eta_mins=combo.eta_mins,
            ),
            items=[
                ComboItem(
                    item_id=combo.main.id,
                    name=combo.main.name,
                    price_inr=combo.main.price_inr,
                    dietary_type=combo.main.dietary_type,
                    category=combo.main.category,
                ),
                ComboItem(
                    item_id=combo.booster.id,
                    name=combo.booster.name,
                    price_inr=combo.booster.price_inr,
                    dietary_type=combo.booster.dietary_type,
                    category=combo.booster.category,
                ),
            ],
            total_price_inr=total_price,
            why_it_fits=build_why_it_fits(combo.main, combo.booster, combo.eta_mins, context),
            match_score=min(0.99, round(0.18 + 0.85 * combo.total_score, 2)),
            dietary_type=combo_diet,
        )
