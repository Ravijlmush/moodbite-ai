"""Warm, friend-like, zero-hallucination copy for combo cards and intros."""

from __future__ import annotations

import hashlib

from app.schemas.catalog import MenuItem
from app.schemas.context import UserContext


def _pick(seed_text: str, options: list[str]) -> str:
    digest = hashlib.blake2b(seed_text.encode("utf-8"), digest_size=4).digest()
    idx = int.from_bytes(digest, "little") % len(options)
    return options[idx]


def build_mood_badge(main: MenuItem, context: UserContext) -> str:
    tags = set(main.mood_tags)
    mood = context.user_state.primary_mood

    if mood == "sluggish_heavy" or ("light_comfort" in tags and main.heavy_index <= 0.35):
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
    """Construct a natural, friend-like 1-sentence reason grounded strictly in verified catalog metadata."""
    mood = context.user_state.primary_mood
    seed = f"{main.id}:{booster.id}:{mood}"
    is_sweet_booster = booster.category == "dessert" or "sweet_treat" in booster.mood_tags
    is_fizzy = "fizzy" in booster.sensory_tags or "fizzy_sweet_kick" in booster.mood_tags
    is_cooling = "cooling" in booster.mood_tags or "digestive" in booster.mood_tags
    easy = main.effort_to_eat == "zero_mess"

    if mood == "tired_and_down":
        if is_fizzy:
            return _pick(
                seed,
                [
                    f"Pure spoon-and-relax comfort with a cold fizz on the side—at your door in {eta_mins} mins.",
                    f"Zero-effort warm comfort plus an ice-cold sip to snap you out of the slump ({eta_mins} mins).",
                ],
            )
        if is_sweet_booster:
            return _pick(
                seed,
                [
                    f"Warm, cozy comfort followed by a sweet bite so tonight ends on a better note ({eta_mins} mins).",
                    f"Easy, no-mess comfort food paired with something sweet to lift your mood in {eta_mins} mins.",
                ],
            )
        return f"Warm, {'no-mess' if easy else 'hearty'} comfort you don't have to overthink—arrives in {eta_mins} mins."

    if mood == "stressed_angry":
        if is_cooling:
            return _pick(
                seed,
                [
                    f"Bold, punchy flavors to burn off the tension, balanced with a chilled sip ({eta_mins} mins).",
                    f"Big flavor and texture for instant stress relief, cooled down by a refreshing drink in {eta_mins} mins.",
                ],
            )
        return f"Punchy, high-texture comfort to take the edge off a rough stretch—reaches you in {eta_mins} mins."

    if mood == "sluggish_heavy":
        return _pick(
            seed,
            [
                f"Gentle, light-on-the-stomach comfort with a soothing sip—easy to finish and here in {eta_mins} mins.",
                f"Warm, uncomplicated food that won't weigh you down, arriving in {eta_mins} mins.",
            ],
        )

    if mood == "celebratory_happy":
        return _pick(
            seed,
            [
                f"Proper treat-yourself pairing that feels like a mini celebration—at your door in {eta_mins} mins.",
                f"Rich, crowd-favorite comfort with a fun sidekick to keep the good energy going ({eta_mins} mins).",
            ],
        )

    if mood == "heartbroken_low":
        return _pick(
            seed,
            [
                f"Soft, warm comfort and a gentle sweet pick-me-up—zero effort required, here in {eta_mins} mins.",
                f"Like a warm hug in a bowl with a sweet finish to make tonight a little softer ({eta_mins} mins).",
            ],
        )

    if mood == "bored_restless":
        return f"Bold, playful flavors with contrasting textures to break the monotony—arriving in {eta_mins} mins."

    return f"{'Easy, zero-mess' if easy else 'Solid'} pairing that hits the spot fast—at your door in {eta_mins} mins."


def build_recommendation_intro(
    context: UserContext,
    count: int,
    *,
    user_message: str = "",
    used_fallback: bool = False,
) -> str:
    msg = user_message.lower()
    diet = context.hard_constraints.dietary_type
    diet_tag = f"{diet} " if diet in ("veg", "jain", "vegan") else ""
    seed = f"{context.session_id}:{context.turn_count}:{msg}"

    if used_fallback:
        return f"Say no more—pulled {count} fast, zero-mess {diet_tag}combos so you don't have to think:"

    # React directly to specific real-life situations mentioned by the user
    if any(w in msg for w in ("meeting", "boss", "work", "office", "deadline")):
        return _pick(
            seed,
            [
                f"Oof, rough work stretch—let food do the heavy lifting. Grab one of these {count} fast {diet_tag}picks:",
                f"Close the laptop for a bit. Here are {count} quick, punchy {diet_tag}combos to wash that off:",
            ],
        )
    if any(w in msg for w in ("coding", "late night", "midnight", "debugging")):
        return f"Late-night fuel sorted—{count} zero-mess {diet_tag}combos you can eat right at your desk:"
    if any(w in msg for w in ("finished exams", "promoted", "won", "hackathon")):
        return f"Huge win! You earned a proper treat—check out these {count} {diet_tag}combos:"
    if any(w in msg for w in ("exam", "study", "studying")):
        return f"Exam brain needs real fuel without the mess. Here are {count} fast {diet_tag}combos:"
    if any(w in msg for w in ("fever", "sick", "unwell", "stomach", "queasy", "bloated")):
        return f"Take it easy—I kept it gentle, warm, and light. These {count} {diet_tag}combos will sit well:"
    if any(w in msg for w in ("breakup", "heartbroken", "lonely", "crying")):
        return f"I've got you tonight. Here are {count} warm, cozy {diet_tag}combos with something sweet on the side:"
    if any(w in msg for w in ("rain", "rainy")):
        return f"Rainy-day cravings are undefeated—pulled {count} warm, nostalgic {diet_tag}combos arriving fast:"
    if context.hard_constraints.max_budget_inr and context.hard_constraints.max_budget_inr <= 210:
        cap = context.hard_constraints.max_budget_inr
        return f"Easy on the wallet—found {count} solid {diet_tag}combos under ₹{cap} arriving fast:"

    mood = context.user_state.primary_mood
    if mood == "tired_and_down":
        return _pick(
            seed,
            [
                f"Say no more—long days call for zero-mess comfort. Pick whichever of these {count} {diet_tag}combos speaks to you:",
                f"I've got dinner handled so you can just crash. Here are {count} fast {diet_tag}comfort combos:",
            ],
        )
    if mood == "stressed_angry":
        return _pick(
            seed,
            [
                f"Deep breath—let bold, spicy food take the edge off. Here are {count} fast {diet_tag}combos:",
                f"Stress calls for crunch and spice. Pulled {count} quick {diet_tag}combos near you:",
            ],
        )
    if mood == "sluggish_heavy":
        return f"Keeping things super light and easy to digest—here are {count} gentle {diet_tag}combos:"
    if mood == "celebratory_happy":
        return f"Love the vibe—here are {count} fun, indulgent {diet_tag}combos to celebrate with:"
    if mood == "heartbroken_low":
        return f"Sending warm comfort your way—here are {count} cozy {diet_tag}combos arriving fast:"
    if mood == "bored_restless":
        return f"Let's wake up your taste buds—{count} punchy {diet_tag}combos coming right up:"

    return _pick(
        seed,
        [
            f"Got you covered—here are {count} fast {diet_tag}combos that fit the moment:",
            f"Sorted! Take your pick from these {count} quick {diet_tag}combos nearby:",
        ],
    )
