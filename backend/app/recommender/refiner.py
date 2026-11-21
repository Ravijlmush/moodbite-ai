"""One-tap refinement chip processor (Spec 06: POST /api/v1/chat/refine)."""

from __future__ import annotations

import re

from app.schemas.context import UserContext

BUDGET_RE = re.compile(r"(?:under|below|max)\s*(?:₹|rs\.?|inr)?\s*(\d{2,4})", re.IGNORECASE)
ETA_RE = re.compile(r"(\d{1,2})\s*(?:m|min|mins|minutes)", re.IGNORECASE)


def apply_refinement_chip(
    context: UserContext,
    chip: str,
    swap_drink_step: int,
) -> tuple[UserContext, int, str]:
    """Deterministically apply a one-tap chip to UserContext without re-running LLM mood extraction."""
    updated = context.model_copy(deep=True)
    new_swap_step = swap_drink_step
    c = chip.strip().lower()

    budget_match = BUDGET_RE.search(c)
    eta_match = ETA_RE.search(c)

    if budget_match:
        cap = max(120, int(budget_match.group(1)))
        updated.hard_constraints.max_budget_inr = cap
        updated.food_preferences.craving_profiles = list(
            dict.fromkeys([*updated.food_preferences.craving_profiles, "budget_friendly"])
        )
        msg = f"Easy on the wallet—kept everything under ₹{cap}:"
    elif "spicier" in c or "spicy" in c:
        updated.food_preferences.spice_tolerance = "high"
        updated.food_preferences.craving_profiles = list(
            dict.fromkeys([*updated.food_preferences.craving_profiles, "bold_spicy", "sensory_release"])
        )
        msg = "Dialed up the spice—here are bolder picks arriving fast:"
    elif "lighter" in c or "light" in c:
        updated.food_preferences.spice_tolerance = "mild"
        updated.food_preferences.portion_size = "light_snack"
        updated.food_preferences.craving_profiles = ["light_comfort", "digestive", "cooling"]
        msg = "Kept it light and easy on the stomach:"
    elif "swap drink" in c or "swap booster" in c or "change drink" in c:
        new_swap_step += 1
        msg = "Swapped out the drinks from the same kitchens—better?"
    elif "sweet" in c or "dessert" in c:
        updated.food_preferences.craving_profiles = list(
            dict.fromkeys([*updated.food_preferences.craving_profiles, "sweet_treat", "cheer_up"])
        )
        msg = "Added sweet pairings to round it out:"
    elif "veg only" in c or c == "veg":
        updated.hard_constraints.dietary_type = "veg"
        msg = "Locked to pure veg combos arriving fast:"
    elif eta_match or "faster" in c:
        target_eta = int(eta_match.group(1)) if eta_match else 22
        updated.hard_constraints.max_eta_mins = max(15, min(target_eta, 30))
        msg = f"Pulled the quickest kitchens under {updated.hard_constraints.max_eta_mins} mins:"
    else:
        msg = f"Tweaked the list for '{chip.strip()}':"

    updated.routing.next_action = "recommend_combos"
    updated.routing.state_confidence = max(updated.routing.state_confidence, 0.90)
    return updated, new_swap_step, msg
