"""Deterministic offline mood, preference & constraint extractor (zero-API-key runtime)."""

from __future__ import annotations

import re

from app.prompts.templates import STARTER_QUICK_REPLY_PILLS
from app.schemas.context import LLMExtractionOutput, UserContext

BUDGET_RE = re.compile(
    r"(?:under|below|within|max|around|budget(?:\s+of)?)\s*(?:₹|rs\.?|inr)?\s*(\d{2,4})(?!\s*(?:m|min|mins|minutes|hr|hrs|hour|hours|km)\b)\b|(?:₹|rs\.?)\s*(\d{2,4})\b",
    re.IGNORECASE,
)
ETA_RE = re.compile(r"(?:within|under|in)\s*(\d{1,2})\s*(?:min|mins|minutes)\b", re.IGNORECASE)

VAGUE_OPENERS = {
    "hi",
    "hello",
    "hey",
    "hii",
    "yo",
    "sup",
    "idk",
    "anything",
    "whatever",
    "not sure",
    "hungry",
    "what should i eat",
    "help",
}


def _contains_any(text: str, keywords: tuple[str, ...]) -> bool:
    return any(re.search(rf"\b{re.escape(kw)}\b", text) if " " not in kw else kw in text for kw in keywords)


def extract_offline_turn(current: UserContext, message: str) -> LLMExtractionOutput:
    """Parse mood, cravings, effort, dietary rules, allergies, and budget deterministically."""
    ctx = current.model_copy(deep=True)
    text = message.lower().strip()
    signal_score = 0.0

    # 1. Dietary detection
    if _contains_any(text, ("jain", "no onion", "no garlic", "without onion")):
        ctx.hard_constraints.dietary_type = "jain"
        signal_score += 0.18
    elif _contains_any(text, ("vegan", "plant based", "plant-based")):
        ctx.hard_constraints.dietary_type = "vegan"
        signal_score += 0.18
    elif _contains_any(text, ("veg only", "pure veg", "vegetarian", "veg")):
        if not _contains_any(text, ("non veg", "non-veg", "nonveg")):
            ctx.hard_constraints.dietary_type = "veg"
            signal_score += 0.15
    elif _contains_any(text, ("halal",)):
        ctx.hard_constraints.dietary_type = "halal"
        signal_score += 0.15
    elif _contains_any(text, ("eggetarian", "egg only")):
        ctx.hard_constraints.dietary_type = "eggetarian"
        signal_score += 0.15
    elif _contains_any(text, ("non veg", "non-veg", "nonveg", "chicken", "mutton")):
        ctx.hard_constraints.dietary_type = "non_veg"
        signal_score += 0.18

    # 2. Allergy & exclusion detection
    allergy_map = {
        "dairy": ("dairy free", "dairy-free", "no dairy", "lactose", "lactose intolerant", "no milk", "dairy allergy"),
        "peanuts": ("peanut allergy", "no peanuts", "no peanut", "allergic to peanuts", "peanut free"),
        "nuts": ("nut allergy", "no nuts", "nut free", "nut-free", "allergic to nuts"),
        "gluten": ("gluten free", "gluten-free", "no gluten", "celiac", "allergic to gluten"),
        "soy": ("soy allergy", "no soy", "soy free", "allergic to soy"),
        "egg": ("egg allergy", "no egg", "no eggs", "allergic to egg"),
    }
    for allergen, phrases in allergy_map.items():
        if _contains_any(text, phrases):
            if allergen not in ctx.hard_constraints.allergies:
                ctx.hard_constraints.allergies.append(allergen)
            signal_score += 0.12

    no_item_match = re.findall(r"\bwithout\s+([a-z]{3,15})\b", text)
    for token in no_item_match:
        if token not in ("onion", "garlic") and token not in ctx.food_preferences.excluded_ingredients:
            ctx.food_preferences.excluded_ingredients.append(token)

    # 3. Budget & ETA urgency detection (check ETA before budget and ignore small time numbers)
    eta_match = ETA_RE.search(text)
    if eta_match:
        ctx.hard_constraints.max_eta_mins = max(15, min(int(eta_match.group(1)), 45))
        signal_score += 0.20
    elif _contains_any(text, ("fast", "asap", "quick", "hurry", "right now", "urgent", "starving", "dying of hunger")):
        ctx.hard_constraints.max_eta_mins = min(ctx.hard_constraints.max_eta_mins, 30)
        signal_score += 0.20

    budget_match = BUDGET_RE.search(text)
    if budget_match:
        val = int(budget_match.group(1) or budget_match.group(2))
        if val >= 80:
            ctx.hard_constraints.max_budget_inr = max(120, min(val, 3000))
            ctx.food_preferences.craving_profiles = list(
                dict.fromkeys([*ctx.food_preferences.craving_profiles, "budget_friendly"])
            )
            signal_score += 0.25

    # 4. Mood, energy, and stress detection (check celebratory & explicit recovery before stress triggers like 'exam')
    mood_detected = ctx.user_state.primary_mood != "neutral_hungry"
    new_mood_detected = False
    if _contains_any(text, ("heartbroken", "breakup", "lonely", "crying", "sad", "depressed", "blue", "miserable")):
        ctx.user_state.primary_mood = "heartbroken_low"
        ctx.user_state.emotional_valence = -0.7
        ctx.user_state.energy_level = "low"
        ctx.user_state.stress_level = "medium"
        ctx.user_state.goal = "comfort_and_cheer_up"
        new_mood_detected = True
        signal_score += 0.45
    elif _contains_any(text, ("sluggish", "heavy", "fever", "sick", "unwell", "stomach", "queasy", "bloated", "recovering", "post-fever", "post fever", "ill", "light & fresh", "light and fresh")):
        ctx.user_state.primary_mood = "sluggish_heavy"
        ctx.user_state.emotional_valence = -0.35
        ctx.user_state.energy_level = "low"
        ctx.user_state.stress_level = "low"
        ctx.user_state.goal = "gentle_recovery"
        ctx.food_preferences.spice_tolerance = "mild"
        ctx.food_preferences.portion_size = "light_snack"
        new_mood_detected = True
        signal_score += 0.50
    elif _contains_any(text, ("celebrate", "celebrating", "celebratory", "finished exams", "promoted", "party", "weekend", "great day", "won", "treat myself", "chill evening")):
        ctx.user_state.primary_mood = "celebratory_happy"
        ctx.user_state.emotional_valence = 0.8
        ctx.user_state.energy_level = "high"
        ctx.user_state.stress_level = "low"
        ctx.user_state.goal = "treat_and_celebrate"
        new_mood_detected = True
        signal_score += 0.55
    elif _contains_any(text, ("stressed", "angry", "awful", "frustrated", "overwhelmed", "anxious", "exam", "meeting", "deadline", "pissed", "irritated", "tense")):
        ctx.user_state.primary_mood = "stressed_angry"
        ctx.user_state.emotional_valence = -0.5
        ctx.user_state.energy_level = "medium"
        ctx.user_state.stress_level = "high"
        ctx.user_state.goal = "sensory_release"
        new_mood_detected = True
        signal_score += 0.45
    elif _contains_any(text, ("tired", "drained", "exhausted", "exhausting", "sleepy", "burned out", "burnout", "mood is off", "mood off", "low energy", "long day", "late night", "coder", "rough day", "cheer me up", "cheer up", "after work")):
        ctx.user_state.primary_mood = "tired_and_down"
        ctx.user_state.emotional_valence = -0.6
        ctx.user_state.energy_level = "low"
        ctx.user_state.stress_level = "medium"
        ctx.user_state.goal = "comfort_and_cheer_up"
        new_mood_detected = True
        signal_score += 0.45
    elif _contains_any(text, ("bored", "surprise me", "monotonous", "something fun", "chatpata", "different")):
        ctx.user_state.primary_mood = "bored_restless"
        ctx.user_state.emotional_valence = 0.05
        ctx.user_state.energy_level = "medium"
        ctx.user_state.stress_level = "low"
        ctx.user_state.goal = "novelty_and_zing"
        new_mood_detected = True
        signal_score += 0.40

    mood_detected = mood_detected or new_mood_detected

    # 5. Craving profile detection
    cravings = list(ctx.food_preferences.craving_profiles)
    craving_detected = False

    def _add_craving(*tags: str) -> None:
        nonlocal craving_detected
        craving_detected = True
        for t in tags:
            if t not in cravings:
                cravings.append(t)

    if _contains_any(text, ("spicy", "spicier", "hot", "chilli", "fiery", "bold", "masala", "tikka")):
        ctx.food_preferences.spice_tolerance = "high"
        _add_craving("bold_spicy", "sensory_release")
        signal_score += 0.35
    if _contains_any(text, ("crunchy", "crispy", "crunch", "roll", "rolls", "wrap")):
        _add_craving("crunchy")
        signal_score += 0.25
    if _contains_any(text, ("light", "fresh", "not oily", "nothing too oily", "nothing oily", "soup", "curd rice", "khichdi", "poha", "easy to digest", "gentle")):
        ctx.food_preferences.spice_tolerance = "mild"
        _add_craving("light_comfort", "cooling", "digestive")
        signal_score += 0.35
    if _contains_any(text, ("comfort", "warm", "homestyle", "rajma", "dal", "biryani", "bowl", "cozy", "nostalgic", "cheer me up", "cheer up", "cheers me up")):
        _add_craving("warm_comfort", "comfort_classic", "nostalgic", "cheer_up")
        signal_score += 0.32
    if _contains_any(text, ("sweet", "dessert", "chocolate", "brownie", "gulab jamun", "cake", "ice cream", "treat", "halwa")):
        _add_craving("sweet_treat", "cheer_up")
        signal_score += 0.30
    if _contains_any(text, ("coke", "cola", "fizzy", "soda", "cold drink", "thums up", "limca", "cheer me up", "cheers me up")):
        _add_craving("fizzy_sweet_kick")
        signal_score += 0.20
    if _contains_any(text, ("no mess", "zero mess", "zero-mess", "easy to eat", "one hand", "spoon")):
        ctx.food_preferences.effort_to_eat = "zero_mess"
        signal_score += 0.35

    # Auto-populate mood-aligned cravings if mood was detected without explicit flavor words
    if mood_detected and not craving_detected:
        if ctx.user_state.primary_mood == "sluggish_heavy":
            _add_craving("light_comfort", "digestive", "cooling")
        elif ctx.user_state.primary_mood == "celebratory_happy":
            _add_craving("sweet_treat", "comfort_classic", "cheer_up")
        elif ctx.user_state.primary_mood == "heartbroken_low":
            _add_craving("warm_comfort", "sweet_treat", "nostalgic")
        elif ctx.user_state.primary_mood == "tired_and_down" and (ctx.hard_constraints.max_eta_mins <= 30 or ctx.hard_constraints.dietary_type):
            _add_craving("warm_comfort", "comfort_classic", "fizzy_sweet_kick")

    ctx.food_preferences.craving_profiles = cravings

    # Low energy invariant (Spec 03 Rule 4)
    if ctx.user_state.energy_level == "low":
        ctx.food_preferences.effort_to_eat = "zero_mess"
        ctx.hard_constraints.max_eta_mins = min(ctx.hard_constraints.max_eta_mins, 30)

    # 6. Confidence & Turn Decision Gate
    cleaned = re.sub(r"[^a-z0-9\s]", "", text).strip()
    is_vague = cleaned in VAGUE_OPENERS or len(cleaned.split()) <= 2 and not new_mood_detected and not craving_detected

    carryover_bonus = 0.25 if (ctx.turn_count >= 2 and (mood_detected or ctx.food_preferences.craving_profiles)) else 0.0
    confidence = min(0.95, max(0.25, 0.22 + signal_score + carryover_bonus))
    if is_vague and ctx.turn_count < 3:
        confidence = min(confidence, 0.45)

    # Trigger recommendations when confidence >= 0.75 or Turn 3 ceiling reached
    if confidence >= 0.75 or ctx.turn_count >= 3:
        ctx.routing.state_confidence = max(confidence, 0.80)
        ctx.routing.next_action = "recommend_combos"
        ctx.routing.clarifying_question = None
        if not ctx.food_preferences.craving_profiles:
            ctx.food_preferences.craving_profiles = ["warm_comfort", "comfort_classic", "fizzy_sweet_kick"]
        return LLMExtractionOutput(
            updated_context=ctx,
            reply_text="Got you—pulling up fast, mood-matched combos near you right now.",
            quick_reply_pills=["Under ₹250", "Make it spicier", "Something lighter", "Swap drink"],
        )

    # Otherwise emit a natural, friend-like <45 word nudge + 4 crisp pills (<=4 words each)
    ctx.routing.state_confidence = round(confidence, 2)
    ctx.routing.next_action = "ask_followup"

    if ctx.turn_count == 1 and not mood_detected and not craving_detected:
        if cleaned in ("hi", "hello", "hey", "hii", "yo", "sup"):
            question = "Hey! Long day or just hungry? Tell me the vibe and I'll sort out food."
        elif "hungry" in text or "starving" in text:
            question = "Say less—what kind of hungry are we talking? Warm comfort, spicy kick, or something light?"
        else:
            question = "No stress, I'll decide for you—just tell me the vibe right now."
        pills = list(STARTER_QUICK_REPLY_PILLS)
    elif ctx.user_state.primary_mood == "stressed_angry":
        question = (
            "Ugh, one of those days. Want fiery, crunchy food to shake off the stress, "
            "or something warm and grounding?"
        )
        pills = ["Spicy & crunchy", "Warm comfort bowl", "Light & cooling", "Veg only, fast"]
    elif ctx.user_state.primary_mood == "tired_and_down":
        question = (
            "Long day—zero-effort food only. Craving a warm nostalgic bowl "
            "or something cheesy and sweet?"
        )
        pills = ["Warm comfort bowl", "Cheesy & indulgent", "Light & simple", "Under ₹250"]
    elif ctx.user_state.primary_mood == "bored_restless":
        question = (
            "Fair—let's keep it interesting. Spicy street-style crunch "
            "or a punchy fusion bowl?"
        )
        pills = ["Spicy street crunch", "Fusion rice bowl", "Sweet treat combo", "Under ₹250"]
    elif ctx.turn_count >= 2:
        question = (
            "Almost there—do you want something warm and comforting, spicy, "
            "or should I just surprise you?"
        )
        pills = ["Warm homestyle", "Bold & spicy", "Light & gentle", "Just surprise me"]
    else:
        question = (
            "Got it—leaning toward warm comfort, something spicy, "
            "or light and easy on the stomach?"
        )
        pills = ["Warm homestyle", "Bold & spicy", "Light & gentle", "Fast under ₹250"]

    ctx.routing.clarifying_question = question
    return LLMExtractionOutput(
        updated_context=ctx,
        reply_text=question,
        quick_reply_pills=pills,
    )
