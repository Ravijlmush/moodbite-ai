"""Deterministic offline mood, preference & constraint extractor (hardened for messy, multilingual & adversarial inputs)."""

from __future__ import annotations

import re

from app.agent.guardrails import (
    detect_medical_flags,
    extract_deterministic_safety_constraints,
    strip_prompt_injection,
)
from app.prompts.templates import STARTER_QUICK_REPLY_PILLS
from app.schemas.context import LLMExtractionOutput, UserContext

BUDGET_RE = re.compile(
    r"(?:under|below|within|max|around|budget(?:\s+of)?)\s*(?:₹|rs\.?|inr)?\s*(\d{2,4})(?!\s*(?:m|min|mins|minutes|hr|hrs|hour|hours|km)\b)\b|(?:₹|rs\.?)\s*(\d{2,4})\b",
    re.IGNORECASE,
)
ETA_RE = re.compile(r"(?:within|under|in)\s*(\d{1,2})\s*(?:min|mins|minutes)\b", re.IGNORECASE)
ELONGATED_RE = re.compile(r"([a-z])\1{2,}", re.IGNORECASE)
PIVOT_RE = re.compile(r"\b(?:but\s+now|actually(?:\s+i'?m|\s+i\s+am)?|instead\s+i'?m|now\s+i'?m)\b(.*)$", re.IGNORECASE)
REJECTION_RE = re.compile(
    r"\b(?:no,?\s*something\s+else|something\s+else|something\s+different|other\s+options|not\s+these|show\s+(?:me\s+)?more|different\s+ones|nah\s+else)\b",
    re.IGNORECASE,
)

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

GIBBERISH_TOKENS = {"asdfghjkl", "qwerty", "zxcvbnm", "asdf", "fdsa", "jjjj"}


def _normalize_typos(text: str) -> str:
    # Collapse 3+ repeated letters (e.g., "sooo" -> "soo"/"so", "stresssed" -> "stressed")
    collapsed = ELONGATED_RE.sub(r"\1\1", text)
    # Also map common double-vowel exaggerations like "sooo" -> "so"
    collapsed = re.sub(r"\bsoo+\b", "so", collapsed)
    collapsed = re.sub(r"\bstress+ed\b", "stressed", collapsed)
    return collapsed


def _contains_any(text: str, keywords: tuple[str, ...]) -> bool:
    for kw in keywords:
        if any(ord(ch) > 127 for ch in kw) or " " in kw:
            if kw in text:
                return True
        else:
            if re.search(rf"\b{re.escape(kw)}\b", text):
                return True
    return False


def is_rejection_followup(message: str) -> bool:
    return bool(message and REJECTION_RE.search(message.strip()))


def derive_mcp_search_queries(ctx: UserContext) -> list[str]:
    """Generate 2-3 specific Swiggy MCP search queries aligned to mood & dietary rules (Spec 10)."""
    diet = ctx.hard_constraints.dietary_type
    mood = ctx.user_state.primary_mood
    cravings = set(ctx.food_preferences.craving_profiles)

    if "vrat" in cravings:
        return ["sabudana khichdi", "vrat paneer", "makhana kheer"]
    if diet == "jain":
        return ["jain dal khichdi", "jain paneer roll", "jain veg pulao"]
    if diet == "vegan":
        return ["dal tadka bowl", "rajma rice bowl", "veg clear soup"]

    if mood == "stressed_angry" or ctx.food_preferences.spice_tolerance == "high":
        if diet in ("veg", None):
            return ["paneer tikka roll", "chilli garlic noodles", "veg momos"]
        return ["chicken tikka roll", "chilli garlic noodles", "biryani bowl"]

    if mood == "sluggish_heavy" or "light_comfort" in cravings:
        return ["curd rice", "clear soup", "moong dal khichdi"]

    if mood == "celebratory_happy":
        if diet == "veg":
            return ["paneer makhani bowl", "dum biryani", "choco lava cake"]
        return ["butter chicken bowl", "chicken biryani", "choco lava cake"]

    if mood == "heartbroken_low":
        return ["rajma chawal", "mac and cheese", "gulab jamun"]

    if mood == "bored_restless":
        return ["pav bhaji", "hakka noodles", "paneer wrap"]

    return ["rajma chawal", "dal khichdi", "paneer roll"]


def extract_offline_turn(current: UserContext, message: str) -> LLMExtractionOutput:
    """Parse mood, cravings, effort, dietary rules, allergies, and budget deterministically."""
    ctx = current.model_copy(deep=True)
    cleaned_msg, _ = strip_prompt_injection(message)
    raw_stripped = cleaned_msg.strip()
    text = _normalize_typos(raw_stripped.lower())
    signal_score = 0.0

    # Empty, whitespace, or pure gibberish check (Stress #16)
    alpha_only = re.sub(r"[^a-z]", "", text)
    if not raw_stripped or text in GIBBERISH_TOKENS or (
        len(alpha_only) >= 7
        and not any(v in alpha_only for v in ("a", "e", "i", "o", "u", "y"))
    ):
        if ctx.turn_count >= 3:
            ctx.routing.state_confidence = 0.80
            ctx.routing.next_action = "recommend_combos"
            ctx.food_preferences.craving_profiles = ["warm_comfort", "comfort_classic", "fizzy_sweet_kick"]
            return LLMExtractionOutput(
                updated_context=ctx,
                reply_text="No worries—let's keep it simple with a few crowd-favorite comfort picks arriving fast:",
                quick_reply_pills=["Under ₹250", "Make it spicier", "Something lighter", "Swap drink"],
            )
        ctx.routing.state_confidence = 0.30
        ctx.routing.next_action = "ask_followup"
        q = "Didn't quite catch that—tell me how you're feeling or tap a mood below:"
        ctx.routing.clarifying_question = q
        return LLMExtractionOutput(
            updated_context=ctx,
            reply_text=q,
            quick_reply_pills=list(STARTER_QUICK_REPLY_PILLS),
        )

    # Rejection / "no, something else" rotation (Stress #27)
    if is_rejection_followup(raw_stripped):
        ctx.routing.state_confidence = max(ctx.routing.state_confidence, 0.88)
        ctx.routing.next_action = "recommend_combos"
        if not ctx.food_preferences.craving_profiles:
            ctx.food_preferences.craving_profiles = ["warm_comfort", "comfort_classic", "fizzy_sweet_kick"]
        return LLMExtractionOutput(
            updated_context=ctx,
            reply_text="Got it—let's switch it up with fresh kitchens you haven't seen yet:",
            quick_reply_pills=["Under ₹250", "Make it spicier", "Something lighter", "Swap drink"],
        )

    # 1. Deterministic dietary, allergy, and meat exclusions (including stacked lists)
    det_diet, det_allergies, det_excluded = extract_deterministic_safety_constraints(raw_stripped)
    if det_diet is not None:
        ctx.hard_constraints.dietary_type = det_diet
        signal_score += 0.22
    elif _contains_any(text, ("non veg", "non-veg", "nonveg", "chicken", "mutton")):
        ctx.hard_constraints.dietary_type = "non_veg"
        signal_score += 0.18

    for allergen in det_allergies:
        if allergen not in ctx.hard_constraints.allergies:
            ctx.hard_constraints.allergies.append(allergen)
        signal_score += 0.15

    for ex in det_excluded:
        if ex not in ctx.food_preferences.excluded_ingredients:
            ctx.food_preferences.excluded_ingredients.append(ex)
        signal_score += 0.15

    if _contains_any(text, ("navratri", "vrat", "upvas", "fasting")):
        if "vrat" not in ctx.food_preferences.craving_profiles:
            ctx.food_preferences.craving_profiles.append("vrat")
        signal_score += 0.30

    # Medical flags (Stress #2, #5, #6)
    medical = detect_medical_flags(raw_stripped)
    if medical["diabetic"]:
        if "__diabetic_safe__" not in ctx.food_preferences.excluded_ingredients:
            ctx.food_preferences.excluded_ingredients.append("__diabetic_safe__")
        signal_score += 0.30
    if medical["pregnant"]:
        if "__pregnancy_safe__" not in ctx.food_preferences.excluded_ingredients:
            ctx.food_preferences.excluded_ingredients.append("__pregnancy_safe__")
        signal_score += 0.30
    if medical["medical_cure_claim"]:
        signal_score += 0.55

    # 2. Budget, calorie & time awareness
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
        if val >= 20:
            # Minimum delivered Main+Booster combo is ₹149; keep filter workable at <=₹200 if user said ₹50
            ctx.hard_constraints.max_budget_inr = 200 if val < 145 else min(val, 3000)
            if "budget_friendly" not in ctx.food_preferences.craving_profiles:
                ctx.food_preferences.craving_profiles.append("budget_friendly")
            signal_score += 0.28

    if _contains_any(text, ("1200 calorie", "calorie diet", "low calorie", "low-calorie", "weight loss")):
        ctx.food_preferences.portion_size = "light_snack"
        if "light_comfort" not in ctx.food_preferences.craving_profiles:
            ctx.food_preferences.craving_profiles.append("light_comfort")
        signal_score += 0.25

    if _contains_any(text, ("3 a.m", "3 am", "3am", "2 a.m", "2am", "4 a.m", "4am", "midnight", "late night")):
        ctx.hard_constraints.max_eta_mins = min(ctx.hard_constraints.max_eta_mins, 30)
        signal_score += 0.22

    # 3. Check for mid-conversation mood pivot ("I was sad, but now I'm okay, actually I'm excited")
    pivot_match = PIVOT_RE.search(text)
    mood_text = pivot_match.group(1).strip() if pivot_match else text
    is_mood_pivot = pivot_match is not None and len(mood_text) >= 3
    if is_mood_pivot:
        # Clear previous mood cravings so the new mood dominates cleanly
        ctx.food_preferences.craving_profiles = [
            c for c in ctx.food_preferences.craving_profiles if c in ("budget_friendly", "vrat")
        ]

    # 4. Mood, energy, and stress detection (English + Hinglish + Hindi Devanagari + Emoji)
    mood_detected = ctx.user_state.primary_mood != "neutral_hungry"
    new_mood_detected = False

    has_tired = _contains_any(
        mood_text,
        (
            "tired", "drained", "exhausted", "exhausting", "sleepy", "burned out", "burnout",
            "mood is off", "mood off", "low energy", "long day", "late night", "coder",
            "rough day", "cheer me up", "cheer up", "after work", "feeling low", "low", "thaka",
            "😴", "🥱", "😩",
        ),
    )
    has_excited_happy = _contains_any(
        mood_text,
        (
            "celebrate", "celebrating", "celebratory", "finished exams", "promoted", "party",
            "weekend", "great day", "won", "treat myself", "chill evening", "happy",
            "excited", "hyped", "thrilled", "pumped", "खुश", "🥳", "🎉", "😄",
        ),
    )
    has_stressed_anxious = _contains_any(
        mood_text,
        (
            "stressed", "angry", "awful", "frustrated", "overwhelmed", "anxious", "anxiety",
            "exam", "meeting", "deadline", "pissed", "irritated", "tense", "burnt out",
            "frazzled", "under pressure", "on edge", "pressure", "तनाव", "गुस्सा",
            "😡", "🤬", "😤", "🤯",
        ),
    )
    has_sad_heartbroken = _contains_any(
        mood_text,
        (
            "heartbroken", "breakup", "lonely", "crying", "sad", "depressed", "blue", "miserable",
            "udas", "उदास", "मन उदास", "दुखी", "😭", "😢", "💔", "😞",
        ),
    )
    has_sluggish = _contains_any(
        mood_text,
        (
            "sluggish", "heavy", "fever", "sick", "unwell", "stomach", "queasy", "bloated",
            "recovering", "post-fever", "post fever", "ill", "light & fresh", "light and fresh",
            "बुखार", "हल्का", "🤒", "🤢",
        ),
    )
    has_bored_meh = _contains_any(
        mood_text,
        ("bored", "surprise me", "monotonous", "something fun", "chatpata", "different", "meh"),
    )

    if has_sluggish:
        ctx.user_state.primary_mood = "sluggish_heavy"
        ctx.user_state.emotional_valence = -0.35
        ctx.user_state.energy_level = "low"
        ctx.user_state.stress_level = "low"
        ctx.user_state.goal = "gentle_recovery"
        ctx.food_preferences.spice_tolerance = "mild"
        ctx.food_preferences.portion_size = "light_snack"
        new_mood_detected = True
        signal_score += 0.50
    elif has_sad_heartbroken and not is_mood_pivot and not (has_tired and has_excited_happy):
        ctx.user_state.primary_mood = "heartbroken_low"
        ctx.user_state.emotional_valence = -0.7
        ctx.user_state.energy_level = "low"
        ctx.user_state.stress_level = "medium"
        ctx.user_state.goal = "comfort_and_cheer_up"
        new_mood_detected = True
        signal_score += 0.55
    elif has_sad_heartbroken and is_mood_pivot:
        ctx.user_state.primary_mood = "heartbroken_low"
        ctx.user_state.emotional_valence = -0.7
        ctx.user_state.energy_level = "low"
        ctx.user_state.stress_level = "medium"
        ctx.user_state.goal = "comfort_and_cheer_up"
        new_mood_detected = True
        signal_score += 0.55
    elif has_tired and has_excited_happy and has_stressed_anxious:
        # Conflicting moods (Stress #15): ground with zero-mess comfort
        ctx.user_state.primary_mood = "tired_and_down"
        ctx.user_state.emotional_valence = 0.0
        ctx.user_state.energy_level = "low"
        ctx.user_state.stress_level = "medium"
        ctx.user_state.goal = "comfort_and_cheer_up"
        new_mood_detected = True
        signal_score += 0.56
    elif has_excited_happy:
        ctx.user_state.primary_mood = "celebratory_happy"
        ctx.user_state.emotional_valence = 0.8
        ctx.user_state.energy_level = "high"
        ctx.user_state.stress_level = "low"
        ctx.user_state.goal = "treat_and_celebrate"
        new_mood_detected = True
        signal_score += 0.55
    elif has_stressed_anxious:
        ctx.user_state.primary_mood = "stressed_angry"
        ctx.user_state.emotional_valence = -0.5
        ctx.user_state.energy_level = "medium"
        ctx.user_state.stress_level = "high"
        ctx.user_state.goal = "sensory_release"
        new_mood_detected = True
        signal_score += 0.55
    elif has_tired:
        ctx.user_state.primary_mood = "tired_and_down"
        ctx.user_state.emotional_valence = -0.6
        ctx.user_state.energy_level = "low"
        ctx.user_state.stress_level = "medium"
        ctx.user_state.goal = "comfort_and_cheer_up"
        new_mood_detected = True
        signal_score += 0.50
    elif has_bored_meh:
        ctx.user_state.primary_mood = "bored_restless"
        ctx.user_state.emotional_valence = 0.05
        ctx.user_state.energy_level = "medium"
        ctx.user_state.stress_level = "low"
        ctx.user_state.goal = "novelty_and_zing"
        new_mood_detected = True
        signal_score += 0.45

    mood_detected = mood_detected or new_mood_detected

    # 5. Craving profile detection (English + Hinglish + Hindi + Emoji)
    cravings = list(ctx.food_preferences.craving_profiles)
    craving_detected = False

    def _add_craving(*tags: str) -> None:
        nonlocal craving_detected
        craving_detected = True
        for t in tags:
            if t not in cravings:
                cravings.append(t)

    if _contains_any(text, ("spicy", "spicier", "hot", "chilli", "fiery", "bold", "masala", "tikka", "teekha", "तीखा", "🌶", "🔥")):
        ctx.food_preferences.spice_tolerance = "high"
        _add_craving("bold_spicy", "sensory_release")
        signal_score += 0.35
    if _contains_any(text, ("crunchy", "crispy", "crunch", "roll", "rolls", "wrap")):
        _add_craving("crunchy")
        signal_score += 0.25
    if _contains_any(text, ("light", "fresh", "not oily", "nothing too oily", "nothing oily", "soup", "curd rice", "khichdi", "poha", "easy to digest", "gentle", "halka", "हल्का")):
        ctx.food_preferences.spice_tolerance = "mild"
        _add_craving("light_comfort", "cooling", "digestive")
        signal_score += 0.35
    if _contains_any(text, ("comfort", "warm", "homestyle", "rajma", "dal", "biryani", "bowl", "cozy", "nostalgic", "cheer me up", "cheer up", "cheers me up", "🍕", "🍔")):
        _add_craving("warm_comfort", "comfort_classic", "nostalgic", "cheer_up")
        signal_score += 0.32
    if _contains_any(text, ("sweet", "dessert", "chocolate", "brownie", "gulab jamun", "cake", "ice cream", "treat", "halwa", "meetha", "मीठा", "🍰", "🍫", "🍦")):
        if not medical["diabetic"]:
            _add_craving("sweet_treat", "cheer_up")
        else:
            _add_craving("light_comfort", "cooling")
        signal_score += 0.30
    if _contains_any(text, ("coke", "cola", "fizzy", "soda", "cold drink", "thums up", "limca", "cheer me up", "cheers me up")):
        if not medical["diabetic"]:
            _add_craving("fizzy_sweet_kick")
        signal_score += 0.20
    if _contains_any(text, ("no mess", "zero mess", "zero-mess", "easy to eat", "one hand", "spoon")):
        ctx.food_preferences.effort_to_eat = "zero_mess"
        signal_score += 0.35

    if _contains_any(text, ("what should i eat", "kuch", "khana", "बताओ", "suggest")):
        signal_score += 0.20

    # Auto-populate mood-aligned cravings if mood was detected without explicit flavor words
    if mood_detected and not craving_detected:
        if ctx.user_state.primary_mood == "sluggish_heavy":
            _add_craving("light_comfort", "digestive", "cooling")
        elif ctx.user_state.primary_mood == "celebratory_happy":
            _add_craving("sweet_treat", "comfort_classic", "cheer_up")
        elif ctx.user_state.primary_mood == "heartbroken_low":
            _add_craving("warm_comfort", "sweet_treat", "nostalgic")
        elif ctx.user_state.primary_mood == "stressed_angry":
            _add_craving("bold_spicy", "crunchy", "warm_comfort")
        elif ctx.user_state.primary_mood == "tired_and_down":
            _add_craving("warm_comfort", "comfort_classic", "fizzy_sweet_kick")

    ctx.food_preferences.craving_profiles = cravings
    ctx.food_preferences.search_queries = derive_mcp_search_queries(ctx)

    # Low energy invariant (Spec 03 Rule 4)
    if ctx.user_state.energy_level == "low":
        ctx.food_preferences.effort_to_eat = "zero_mess"
        ctx.hard_constraints.max_eta_mins = min(ctx.hard_constraints.max_eta_mins, 30)

    # 6. Confidence & Turn Decision Gate
    cleaned = re.sub(r"[^a-z0-9\s]", "", text).strip()
    is_vague = (
        cleaned in VAGUE_OPENERS
        or (len(cleaned.split()) <= 2 and not new_mood_detected and not craving_detected and not any(ord(c) > 127 for c in raw_stripped))
    )

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
