"""On-the-fly live Swiggy Food MCP catalog enrichment, filtering & combo ranking (Spec 10 Section 5)."""

from __future__ import annotations

import asyncio
from typing import Any

from app.agent.nlg import build_mood_badge, build_why_it_fits
from app.mcp.swiggy_client import SwiggyFoodMCPClient, SwiggyMCPError
from app.recommender.embeddings import EmbeddingService, cosine_similarity
from app.recommender.engine import item_is_allergy_safe, item_matches_dietary
from app.schemas.catalog import (
    CatalogDietaryType,
    ComboItem,
    ComboRecommendation,
    ComboRestaurant,
    ItemCategory,
    MenuItem,
    Restaurant,
)
from app.schemas.context import UserContext

ZERO_MESS_KEYWORDS = ("bowl", "roll", "wrap", "biryani", "khichdi", "rice", "soup", "noodle", "maggi", "poha", "idli")
BEVERAGE_KEYWORDS = ("coke", "cola", "pepsi", "limca", "sprite", "thums up", "chaas", "lassi", "lemonade", "soda", "tea", "coffee", "juice", "cooler", "milk", "shake")
DESSERT_KEYWORDS = ("gulab jamun", "brownie", "lava cake", "cake", "halwa", "kheer", "ladoo", "ice cream", "pudding", "mousse", "cookie", "jamun")


class SwiggyMCPUnavailable(Exception):
    """Raised when live Swiggy Food MCP search fails, times out (>3s), or returns insufficient combos."""


def _infer_category(name: str, raw_cat: str) -> ItemCategory:
    low = f"{name} {raw_cat}".lower()
    if any(k in low for k in BEVERAGE_KEYWORDS):
        return "beverage"
    if any(k in low for k in DESSERT_KEYWORDS):
        return "dessert"
    if "roll" in low or "wrap" in low or "kathi" in low:
        return "roll_wrap"
    if "biryani" in low or "pulao" in low:
        return "biryani_rice"
    if "noodle" in low or "soup" in low or "maggi" in low:
        return "noodle_soup"
    if "bowl" in low or "khichdi" in low or "rice" in low:
        return "main_bowl"
    return "comfort_plate"


def _infer_dietary_type(raw_item: dict[str, Any]) -> CatalogDietaryType:
    if raw_item.get("is_veg") is True or raw_item.get("veg") is True:
        return "veg"
    dt = str(raw_item.get("dietary_type", "")).lower()
    if dt in ("veg", "egg", "non_veg"):
        return dt  # type: ignore[return-value]
    name = str(raw_item.get("name", "")).lower()
    if any(w in name for w in ("chicken", "mutton", "fish", "prawn", "keema", "meat", "lamb", "beef", "pork")):
        return "non_veg"
    if "egg" in name:
        return "egg"
    return "veg"


def _infer_allergens(name: str) -> list[str]:
    low = name.lower()
    allergens: list[str] = []
    if any(w in low for w in ("paneer", "cheese", "butter", "ghee", "makhani", "curd", "chaas", "lassi", "kheer", "cream", "milk", "gulab jamun")):
        if "vegan" not in low:
            allergens.append("dairy")
    if any(w in low for w in ("peanut",)):
        allergens.append("peanuts")
    if any(w in low for w in ("almond", "badam", "cashew", "nut", "pista", "walnut")):
        allergens.append("nuts")
    if any(w in low for w in ("naan", "roti", "paratha", "kulcha", "roll", "wrap", "noodle", "mac", "brownie", "cake", "cookie", "pav")):
        allergens.append("gluten")
    if any(w in low for w in ("tofu", "soy", "soya", "teriyaki", "schezwan", "manchurian")):
        allergens.append("soy")
    if "egg" in low:
        allergens.append("egg")
    return allergens


def _infer_mood_tags(name: str, category: ItemCategory) -> list[str]:
    low = name.lower()
    tags: list[str] = []
    if any(w in low for w in ("rajma", "khichdi", "dal", "chole", "curd rice", "pongal", "homestyle")):
        tags.extend(["comfort_classic", "nostalgic", "tired_and_down", "cheer_up"])
    if any(w in low for w in ("spicy", "chilli", "tikka", "peri", "schezwan", "masala", "65")):
        tags.extend(["stressed_angry", "bold_spicy", "sensory_release"])
    if any(w in low for w in ("curd", "soup", "poha", "idli", "khichdi", "rasam")):
        tags.extend(["sluggish_heavy", "light_comfort"])
    if any(w in low for w in ("coke", "cola", "thums up", "limca", "sprite", "soda", "fizz")):
        tags.extend(["fizzy_sweet_kick", "cheer_up"])
    if any(w in low for w in ("chaas", "lemonade", "mint", "lime", "cooler", "tea")):
        tags.extend(["cooling", "digestive", "light_comfort"])
    if category == "dessert" or any(w in low for w in ("brownie", "lava", "gulab jamun", "halwa", "kheer")):
        tags.extend(["sweet_treat", "celebratory_happy", "heartbroken_low"])
    if not tags:
        tags.extend(["comfort_classic", "cheer_up"])
    return list(dict.fromkeys(tags))


class SwiggyLiveRanker:
    """Enriches live Swiggy Food MCP menus and scores combos in <80 ms."""

    def __init__(self, embedder: EmbeddingService | None = None) -> None:
        self.embedder = embedder or EmbeddingService()

    async def recommend_live(
        self,
        *,
        client: SwiggyFoodMCPClient,
        context: UserContext,
        address_id: str,
        user_message: str = "",
        limit: int = 4,
    ) -> list[ComboRecommendation]:
        queries = list(context.food_preferences.search_queries or ["rajma chawal", "dal khichdi", "paneer roll"])[:3]
        try:
            raw_batches = await asyncio.gather(
                *[client.search_craving_dishes(q, address_id) for q in queries],
                return_exceptions=True,
            )
        except Exception as exc:
            raise SwiggyMCPUnavailable(f"Swiggy MCP search failed: {exc}") from exc

        restaurants: dict[str, tuple[Restaurant, int]] = {}
        mains_by_rest: dict[str, list[MenuItem]] = {}
        boosters_by_rest: dict[str, list[MenuItem]] = {}
        seen_item_ids: set[str] = set()

        for batch in raw_batches:
            if isinstance(batch, Exception) or not isinstance(batch, list):
                continue
            for entry in batch:
                if not isinstance(entry, dict):
                    continue
                self._ingest_entry(entry, restaurants, mains_by_rest, boosters_by_rest, seen_item_ids)

        # Fetch full restaurant menus for top candidate restaurants lacking boosters
        need_boosters = [
            rid
            for rid in mains_by_rest
            if not boosters_by_rest.get(rid)
        ][:4]
        if need_boosters:
            menus = await asyncio.gather(
                *[client.get_restaurant_menu(rid, address_id) for rid in need_boosters],
                return_exceptions=True,
            )
            for rid, menu_payload in zip(need_boosters, menus):
                if isinstance(menu_payload, dict):
                    for raw_it in menu_payload.get("items") or menu_payload.get("menu") or []:
                        if isinstance(raw_it, dict):
                            raw_it.setdefault("restaurant_id", rid)
                            self._ingest_entry(raw_it, restaurants, mains_by_rest, boosters_by_rest, seen_item_ids)

        if not restaurants or not mains_by_rest:
            raise SwiggyMCPUnavailable("Swiggy MCP returned no matching restaurants")

        query_vec = self.embedder.embed_user_context(context, user_message=user_message)
        dietary = context.hard_constraints.dietary_type
        allergies = context.hard_constraints.allergies
        excluded = context.food_preferences.excluded_ingredients
        budget = context.hard_constraints.max_budget_inr
        max_eta = context.hard_constraints.max_eta_mins

        candidates: list[tuple[float, MenuItem, MenuItem | None, Restaurant, int]] = []
        for rid, (rest, eta) in restaurants.items():
            if not rest.is_open or eta > max_eta:
                continue
            valid_mains = [
                m
                for m in mains_by_rest.get(rid, [])
                if m.is_available and item_matches_dietary(m, dietary) and item_is_allergy_safe(m, allergies, excluded)
            ]
            valid_boosters = [
                b
                for b in boosters_by_rest.get(rid, [])
                if b.is_available and item_matches_dietary(b, dietary) and item_is_allergy_safe(b, allergies, excluded)
            ]
            for main in valid_mains:
                s_mood = cosine_similarity(query_vec, self.embedder.embed_item(main))
                s_eta = max(0.0, min(1.0, 1.0 - (eta / 45.0)))
                s_effort = 1.0 if (context.user_state.energy_level == "low" and main.effort_to_eat == "zero_mess") else 0.5
                s_rating = max(0.0, min(1.0, (rest.rating - 3.0) / 2.0))

                affordable_boosters = [
                    b for b in valid_boosters if budget is None or (main.price_inr + b.price_inr) <= budget
                ]
                if affordable_boosters:
                    booster = affordable_boosters[0]
                    s_affinity = 1.0
                elif budget is None or main.price_inr <= budget:
                    booster = None
                    s_affinity = 0.4
                else:
                    continue

                score = 0.40 * s_mood + 0.25 * s_eta + 0.15 * s_effort + 0.10 * s_rating + 0.10 * s_affinity
                candidates.append((score, main, booster, rest, eta))

        candidates.sort(key=lambda x: x[0], reverse=True)
        chosen: list[ComboRecommendation] = []
        used_rests: set[str] = set()
        for score, main, booster, rest, eta in candidates:
            if rest.id in used_rests:
                continue
            used_rests.add(rest.id)
            items = [
                ComboItem(
                    item_id=main.id,
                    name=main.name,
                    price_inr=main.price_inr,
                    dietary_type=main.dietary_type,
                    category=main.category,
                )
            ]
            total_price = main.price_inr
            title = main.name
            why = (
                build_why_it_fits(main, booster, eta, context)
                if booster is not None
                else f"Zero-effort live Swiggy pick arriving warm in {eta} mins."
            )
            if booster is not None:
                items.append(
                    ComboItem(
                        item_id=booster.id,
                        name=booster.name,
                        price_inr=booster.price_inr,
                        dietary_type=booster.dietary_type,
                        category=booster.category,
                    )
                )
                total_price += booster.price_inr
                title = f"{main.name} + {booster.name}"

            combo_id = f"cmb_{rest.id}_{main.id}_{booster.id if booster else 'solo'}"
            chosen.append(
                ComboRecommendation(
                    combo_id=combo_id,
                    mood_badge=build_mood_badge(main, context),
                    title=title,
                    restaurant=ComboRestaurant(id=rest.id, name=rest.name, rating=rest.rating, eta_mins=eta),
                    items=items,
                    total_price_inr=total_price,
                    why_it_fits=why,
                    match_score=min(0.99, round(0.20 + 0.80 * score, 2)),
                    dietary_type=main.dietary_type,
                    source="swiggy_mcp_live",
                )
            )
            if len(chosen) >= max(3, min(5, limit)):
                break

        if len(chosen) < 1:
            raise SwiggyMCPUnavailable("No live Swiggy combos satisfied hard constraints")

        # Best-effort live coupon enrichment (Spec 10 Section 3.3)
        try:
            coupons = await client.fetch_food_coupons(chosen[0].restaurant.id, address_id)
            if coupons and isinstance(coupons[0], dict):
                code = coupons[0].get("coupon_code") or coupons[0].get("code") or coupons[0].get("title")
                if code:
                    chosen[0].coupon_badge = str(code)[:28]
        except Exception:
            pass

        return chosen

    def _ingest_entry(
        self,
        entry: dict[str, Any],
        restaurants: dict[str, tuple[Restaurant, int]],
        mains_by_rest: dict[str, list[MenuItem]],
        boosters_by_rest: dict[str, list[MenuItem]],
        seen_item_ids: set[str],
    ) -> None:
        rest_raw = entry.get("restaurant") if isinstance(entry.get("restaurant"), dict) else {}
        rid = str(entry.get("restaurant_id") or rest_raw.get("id") or "swiggy_rest")
        rname = str(entry.get("restaurant_name") or rest_raw.get("name") or "Nearby Swiggy Kitchen")
        rating = float(entry.get("restaurant_rating") or rest_raw.get("rating") or 4.3)
        eta = int(entry.get("sla_mins") or entry.get("eta_mins") or rest_raw.get("sla_mins") or rest_raw.get("eta_mins") or 24)
        is_open = bool(entry.get("is_open", rest_raw.get("is_open", True)))

        if rid not in restaurants:
            restaurants[rid] = (
                Restaurant(id=rid, name=rname, rating=max(1.0, min(5.0, rating)), lat=28.6139, lng=77.2090, base_prep_mins=max(5, eta - 10), is_open=is_open),
                eta,
            )

        # If entry wraps a list of menu items
        nested_items = entry.get("items") or entry.get("menu_items")
        if isinstance(nested_items, list):
            for sub in nested_items:
                if isinstance(sub, dict):
                    sub.setdefault("restaurant_id", rid)
                    sub.setdefault("restaurant_name", rname)
                    sub.setdefault("sla_mins", eta)
                    sub.setdefault("restaurant_rating", rating)
                    self._ingest_entry(sub, restaurants, mains_by_rest, boosters_by_rest, seen_item_ids)
            return

        item_id = str(entry.get("item_id") or entry.get("id") or "")
        name = str(entry.get("name") or "").strip()
        if not item_id or not name or item_id in seen_item_ids:
            return
        seen_item_ids.add(item_id)

        price = int(entry.get("price_inr") or entry.get("price") or 180)
        if price > 2500:  # handle paise payloads if raw Swiggy API returns paise
            price = max(20, price // 100)

        cat = _infer_category(name, str(entry.get("category", "")))
        diet = _infer_dietary_type(entry)
        effort = "zero_mess" if any(k in name.lower() for k in ZERO_MESS_KEYWORDS) else "standard"
        tags = list(entry.get("mood_tags") or _infer_mood_tags(name, cat))
        dietary_tags = ["veg"] if diet == "veg" else []
        if "jain" in name.lower():
            dietary_tags.append("jain")
        if "vegan" in name.lower():
            dietary_tags.append("vegan")

        menu_item = MenuItem(
            id=item_id,
            restaurant_id=rid,
            name=name,
            category=cat,
            dietary_type=diet,
            dietary_tags=dietary_tags,
            allergens=list(entry.get("allergens") or _infer_allergens(name)),
            price_inr=max(1, price),
            mood_tags=tags,
            sensory_tags=["warm"] if cat != "beverage" else ["chilled"],
            effort_to_eat=effort,  # type: ignore[arg-type]
            is_available=bool(entry.get("is_available", True)),
        )
        if cat in ("beverage", "dessert"):
            boosters_by_rest.setdefault(rid, []).append(menu_item)
        else:
            mains_by_rest.setdefault(rid, []).append(menu_item)
