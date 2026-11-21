"""Warm, zero-hallucination Natural Language Generation for combo cards & intros."""

from __future__ import annotations

from app.schemas.catalog import MenuItem
from app.schemas.context import UserContext


def build_mood_badge(main: MenuItem, context: UserContext) -> str:
    tags = set(main.mood_tags)
    mood = context.user_state.primary_mood

    if mood == "sluggish_heavy" or "light_comfort" in tags and main.heavy_index <= 0.35:
        return "LIGHT & WARM"
    if mood == "stressed_angry" and ("bold_spicy" in tags or "sensory_release" in tags):
        return "SPICY RELEASE" if main.category != "roll_wrap" else "ZERO-MESS ROLL"
    if context.hard_constraints.max_budget_inr and context.hard_constraints.max_budget_inr <= 210:
        return "BUDGET COMFORT"
    if mood == "celebratory_happy":
        return "CELEBRATION TREAT"
    if mood == "heartbroken_low":
        return "WARM PICK-ME-UP"
    if main.category == "roll_wrap":
        return "ZERO-MESS ROLL"
    if "comfort_classic" in tags or "nostalgic" in tags:
        return "COMFORT CLASSIC"
    if "fizzy_sweet_kick" in tags or "cheer_up" in tags:
        return "MOOD BOOSTER"
    return "FAST COMFORT"


def build_why_it_fits(
    main: MenuItem,
    booster: MenuItem,
    eta_mins: int,
    context: UserContext,
) -> str:
    """Construct a crisp 1-sentence reason strictly grounded in verified catalog metadata."""
    mood = context.user_state.primary_mood
    effort_phrase = "Zero-mess" if main.effort_to_eat == "zero_mess" else "Satisfying"
    is_sweet_booster = booster.category == "dessert" or "sweet_treat" in booster.mood_tags
    is_fizzy = "fizzy" in booster.sensory_tags or "fizzy_sweet_kick" in booster.mood_tags
    is_cooling = "cooling" in booster.mood_tags or "digestive" in booster.mood_tags

    if mood == "tired_and_down":
        if is_fizzy:
            return f"{effort_phrase}, warm comfort paired with a cold fizzy kick arriving in {eta_mins} mins."
        if is_sweet_booster:
            return f"{effort_phrase} homestyle comfort with a sweet finish to lift a tired mood in {eta_mins} mins."
        return f"{effort_phrase}, low-effort meal that reaches your door warm in {eta_mins} mins."

    if mood == "stressed_angry":
        if is_cooling:
            return f"Bold, satisfying flavors balanced with a cooling sip to take the edge off in {eta_mins} mins."
        return f"High-texture, flavor-packed bite ready for instant stress relief in {eta_mins} mins."

    if mood == "sluggish_heavy":
        return f"Gentle, light-on-the-stomach pairing with a soothing sip arriving in {eta_mins} mins."

    if mood == "celebratory_happy":
        return f"Indulgent crowd-pleaser paired with a treat to celebrate right in {eta_mins} mins."

    if mood == "heartbroken_low":
        return f"Warm, cozy comfort and a gentle sweet pick-me-up delivered in {eta_mins} mins."

    if mood == "bored_restless":
        return f"Punchy, playful flavors with contrasting textures to wake up your palate in {eta_mins} mins."

    return f"{effort_phrase} combo matched to your current vibe and arriving in {eta_mins} mins."


def build_recommendation_intro(context: UserContext, count: int, used_fallback: bool = False) -> str:
    diet_label = ""
    if context.hard_constraints.dietary_type in ("veg", "jain", "vegan"):
        diet_label = f"{context.hard_constraints.dietary_type} "

    if used_fallback:
        return (
            f"Say no more—no-mess {diet_label}comfort food coming right up. "
            f"Here are {count} fast combos near you:"
        )

    mood = context.user_state.primary_mood
    if mood == "tired_and_down":
        return (
            f"Say no more—zero-effort {diet_label}comfort food coming right up. "
            f"Here are {count} fast combos near you built to lift a tired mood:"
        )
    if mood == "stressed_angry":
        return (
            f"Deep breath—let good food take the edge off. "
            f"Here are {count} bold, fast {diet_label}combos near you:"
        )
    if mood == "sluggish_heavy":
        return (
            f"Keeping it gentle and easy to digest. "
            f"Here are {count} light, warm {diet_label}combos arriving fast:"
        )
    if mood == "celebratory_happy":
        return (
            f"Love that energy! Here are {count} crowd-pleasing {diet_label}combos "
            "to keep the good vibes rolling:"
        )
    if mood == "heartbroken_low":
        return (
            f"Sending warm comfort your way. Here are {count} cozy {diet_label}combos "
            "and sweet pick-me-ups near you:"
        )
    if mood == "bored_restless":
        return (
            f"Time to shake up the monotony. Here are {count} punchy {diet_label}combos "
            "arriving fast:"
        )
    return f"Got you—here are {count} fast, mood-matched {diet_label}combos ready near you:"
