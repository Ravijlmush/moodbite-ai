"""Deterministic safety, dietary lock, crisis, sanitization, prompt-injection, and zero-hallucination guardrails (Spec 07)."""

from __future__ import annotations

import html
import re
from typing import Optional

from app.prompts.templates import (
    CRISIS_HELPLINES,
    CRISIS_SUPPORT_MESSAGE,
    DISORDERED_EATING_SUPPORT_MESSAGE,
    HARMFUL_REFUSAL_MESSAGE,
)
from app.recommender.catalog_repo import CatalogRepository
from app.recommender.engine import item_is_allergy_safe, item_matches_dietary
from app.schemas.api import ActiveFilters, ChatTurnResponse, UserContextSummary
from app.schemas.catalog import ComboRecommendation
from app.schemas.context import DietaryType, UserContext

# Idioms that look dramatic about hunger/food but are NOT self-harm crises
HUNGER_IDIOM_RE = re.compile(
    r"\b(?:dying\s+(?:of|from|for)|starving\s+to\s+death|kill\s+for\s+(?:food|biryani|pizza|chai|coffee|momos|rajma))\b",
    re.IGNORECASE,
)

# High-precision crisis phrases (suicide / self-harm)
CRISIS_RE = re.compile(
    r"(?:"
    r"\bkill(?:ing)?\s+myself\b|"
    r"\bend(?:ing)?\s+(?:my|it\s+all|this)\s*(?:life)?\b|"
    r"\bsuicid(?:e|al)\b|"
    r"\bself[\s-]?harm\b|"
    r"\bhurt(?:ing)?\s+myself\b|"
    r"\bharm(?:ing)?\s+myself\b|"
    r"\bcut(?:ting)?\s+myself\b|"
    r"\bwant\s+to\s+die\b|"
    r"\bwish\s+i\s+(?:was|were)\s+dead\b|"
    r"\bdon'?t\s+want\s+to\s+live\b|"
    r"\bno\s+reason\s+to\s+live\b|"
    r"\btake\s+my\s+own\s+life\b"
    r")",
    re.IGNORECASE,
)

# Disordered-eating / prolonged food refusal / self-punishment signals (Stress #3 & #4)
DISORDERED_EATING_RE = re.compile(
    r"(?:"
    r"\b(?:so\s+)?depressed\b.{0,50}\b(?:don'?t|do\s+not|can'?t)\s+want\s+to\s+eat\b.{0,30}\bdays\b|"
    r"\b(?:don'?t|do\s+not|won'?t)\s+want\s+to\s+eat\s+(?:anything\s+)?for\s+days\b|"
    r"\bhaven'?t\s+eaten\s+in\s+days\b|"
    r"\bstarv(?:e|ing)\s+myself\b|"
    r"\bfeel\s+worthless\b|"
    r"\bpunish\s+myself\b|"
    r"\beat\s+nothing\b.{0,30}\bpunish\b|"
    r"\bdon'?t\s+deserve\s+to\s+eat\b"
    r")",
    re.IGNORECASE,
)

# Harmful / poisoning intent (Stress #10)
HARMFUL_REQUEST_RE = re.compile(
    r"(?:"
    r"\bpoison(?:ous|ing|ed)?\b|"
    r"\b(?:lace|spike)\s+(?:food|drink|meal|water)\b|"
    r"\bmake\s+(?:someone|people|them|him|her)\s+sick\b|"
    r"\btoxic\s+(?:food|meal|dish|ingredient)\b|"
    r"\b(?:cyanide|arsenic|rat\s+poison|antifreeze)\b|"
    r"\b(?:kill|harm)\s+someone\b"
    r")",
    re.IGNORECASE,
)

# Medical cure claims, diabetes, pregnancy flags (Stress #2, #5, #6)
MEDICAL_CURE_RE = re.compile(
    r"(?:"
    r"\bcur(?:e|es|ing)\s+(?:my\s+)?(?:anxiety|depression|diabetes|stress|mental\s+illness|disease|disorder)\b|"
    r"\bpermanently\s+cure\b|"
    r"\btreat\s+(?:anxiety|depression|diabetes)\s+permanently\b|"
    r"\bfood\s+(?:that\s+)?cures\b"
    r")",
    re.IGNORECASE,
)
DIABETIC_RE = re.compile(r"\b(?:diabetic|diabetes|high\s+blood\s+sugar|insulin)\b", re.IGNORECASE)
PREGNANT_RE = re.compile(r"\b(?:pregnant|pregnancy|expecting\s+a\s+baby|trimester)\b", re.IGNORECASE)

# Prompt injection / roleplay hijack / brand override (Stress #7, #8, #9)
INJECTION_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"ignore\s+(?:all\s+)?previous\s+instructions.*?(?:$|\.)", re.IGNORECASE),
    re.compile(r"(?:print|reveal|show|dump|repeat)\s+(?:your\s+)?system\s+prompt.*?(?:$|\.)", re.IGNORECASE),
    re.compile(r"you\s+are\s+now\s+a\s+[a-z\s]+?(?:,|\.|and|$)", re.IGNORECASE),
    re.compile(r"forget\s+(?:the\s+)?food(?:\s+stuff)?.*?(?:$|\.)", re.IGNORECASE),
    re.compile(r"write\s+me\s+a\s+poem.*?(?:$|\.)", re.IGNORECASE),
    re.compile(r"</?\s*(?:mood|system|assistant|user|prompt)\s*>", re.IGNORECASE),
    re.compile(r"\bSYSTEM\s*:.*$", re.IGNORECASE),
    re.compile(r"recommend\s+only\s+\[?[^\].\n]+\]?(?:\s+from\s+now\s+on)?", re.IGNORECASE),
]

# Sanitization for HTML/XSS and SQL injection fragments (Stress #30)
SCRIPT_BLOCK_RE = re.compile(r"<\s*script[^>]*>.*?<\s*/\s*script\s*>", re.IGNORECASE | re.DOTALL)
HTML_TAG_RE = re.compile(r"<[^>]{1,120}>")
SQLI_RE = re.compile(
    r"(?:';|--\s*$|\bDROP\s+TABLE\b|\bDELETE\s+FROM\b|\bUNION\s+SELECT\b|\bINSERT\s+INTO\b)",
    re.IGNORECASE,
)

# Explicit user cancellation of an earlier dietary lock
CANCEL_VEG_RE = re.compile(
    r"\b(?:non[\s-]?veg\s+(?:is\s+fine|okay|ok|works)|eat\s+(?:meat|chicken|anything)|remove\s+veg|no\s+diet\s+restriction|all\s+meat)\b",
    re.IGNORECASE,
)

SHAMING_WORDS_RE = re.compile(
    r"\b(?:unhealthy|junk\s+food|too\s+much\s+sugar|high\s+calories|guilty\s+pleasure|bad\s+for\s+you|weight\s+gain)\b",
    re.IGNORECASE,
)

LEAK_GUARD_RE = re.compile(
    r"(?:MASTER_SYSTEM_PROMPT|CORE\s+PERSONALITY|CONVERSATION\s+FLOW|updated_context|state_confidence|quick_reply_pills|Arrr|ahoy|matey)",
    re.IGNORECASE,
)


def sanitize_user_input(raw: str) -> str:
    """Strip HTML/script tags, null bytes, and SQL injection payloads safely."""
    if not raw:
        return ""
    cleaned = raw.replace("\x00", "")
    cleaned = SCRIPT_BLOCK_RE.sub(" ", cleaned)
    cleaned = HTML_TAG_RE.sub(" ", cleaned)
    cleaned = html.unescape(cleaned)
    cleaned = SQLI_RE.sub(" ", cleaned)
    cleaned = " ".join(cleaned.split())
    return cleaned


def strip_prompt_injection(message: str) -> tuple[str, bool]:
    """Remove adversarial prompt-injection instructions while keeping the genuine mood/food intent."""
    if not message:
        return "", False
    had_injection = False
    cleaned = message
    for pat in INJECTION_PATTERNS:
        if pat.search(cleaned):
            had_injection = True
            cleaned = pat.sub(" ", cleaned)
    cleaned = " ".join(cleaned.split()).strip(" ,.;:")
    return cleaned, had_injection


def classify_crisis(message: str) -> tuple[bool, str]:
    """Return (is_crisis, crisis_kind: 'self_harm' | 'disordered_eating' | '')."""
    if not message:
        return False, ""
    stripped = HUNGER_IDIOM_RE.sub("", message)
    if CRISIS_RE.search(stripped):
        return True, "self_harm"
    if DISORDERED_EATING_RE.search(stripped):
        return True, "disordered_eating"
    return False, ""


def detect_crisis(message: str) -> bool:
    is_crisis, _ = classify_crisis(message)
    return is_crisis


def detect_harmful_request(message: str) -> bool:
    return bool(message and HARMFUL_REQUEST_RE.search(message))


def detect_medical_flags(message: str) -> dict[str, bool]:
    if not message:
        return {"medical_cure_claim": False, "diabetic": False, "pregnant": False}
    return {
        "medical_cure_claim": bool(MEDICAL_CURE_RE.search(message)),
        "diabetic": bool(DIABETIC_RE.search(message)),
        "pregnant": bool(PREGNANT_RE.search(message)),
    }


def extract_deterministic_safety_constraints(
    message: str,
) -> tuple[Optional[DietaryType], list[str], list[str]]:
    """Deterministically parse stacked allergies, dietary locks, and excluded meats even in LLM mode."""
    text = message.lower()
    dietary: Optional[DietaryType] = None
    allergies: list[str] = []
    excluded: list[str] = []

    if re.search(r"\b(?:jain|navratri|vrat|upvas|no\s+onion|no\s+garlic|without\s+onion)\b", text):
        dietary = "jain"
    elif re.search(r"\b(?:vegan|plant[\s-]?based)\b", text):
        dietary = "vegan"
    elif re.search(r"\b(?:veg\s+only|pure\s+veg|vegetarian)\b", text) or (
        re.search(r"\bveg\b", text) and not re.search(r"\bnon[\s-]?veg\b", text)
    ):
        dietary = "veg"
    elif re.search(r"\bhalal\b", text):
        dietary = "halal"
    elif re.search(r"\b(?:eggetarian|egg\s+only)\b", text):
        dietary = "eggetarian"

    # Parse stacked allergy lists like "allergic to peanuts, dairy and gluten"
    allergy_clause_match = re.search(
        r"(?:allergic\s+to|allergies(?:\s+to)?|intolerant\s+to|cannot\s+have|can'?t\s+have|avoid)\s+([^.!?;\n]+)",
        text,
    )
    known_allergens = {
        "peanuts": ("peanut", "peanuts"),
        "dairy": ("dairy", "milk", "lactose", "casein", "whey"),
        "gluten": ("gluten", "wheat", "celiac"),
        "nuts": ("nut", "nuts", "tree nut", "tree nuts", "almond", "cashew"),
        "soy": ("soy", "soya"),
        "egg": ("egg", "eggs"),
        "sesame": ("sesame",),
    }

    search_space = allergy_clause_match.group(1) if allergy_clause_match else text
    for canonical, terms in known_allergens.items():
        if allergy_clause_match:
            if any(re.search(rf"\b{re.escape(t)}\b", search_space) for t in terms):
                if canonical not in allergies:
                    allergies.append(canonical)
        else:
            matched = False
            for t in terms:
                if re.search(
                    rf"\b(?:no\s+{re.escape(t)}|{re.escape(t)}[\s-]*(?:free|allergy|intoleran\w*))\b",
                    text,
                ):
                    matched = True
                    break
            if canonical == "dairy" and "lactose" in text:
                matched = True
            if canonical == "gluten" and "celiac" in text:
                matched = True
            if matched and canonical not in allergies:
                allergies.append(canonical)

    # Religious / personal meat exclusions (Stress #23: "can't eat beef or pork")
    for meat in ("beef", "pork", "bacon", "ham", "shellfish", "seafood", "mushroom", "onion", "garlic"):
        if re.search(rf"\b(?:no|avoid|can'?t\s+eat|cannot\s+eat|don'?t\s+eat|without)\b[^.!?\n]{{0,30}}\b{meat}\b", text):
            if meat not in excluded:
                excluded.append(meat)

    return dietary, allergies, excluded


def build_context_summary(ctx: UserContext) -> UserContextSummary:
    return UserContextSummary(
        primary_mood=ctx.user_state.primary_mood,
        energy_level=ctx.user_state.energy_level,
        effort_to_eat=ctx.food_preferences.effort_to_eat,
        max_eta_mins=ctx.hard_constraints.max_eta_mins,
        dietary_type=ctx.hard_constraints.dietary_type,
        allergies=list(ctx.hard_constraints.allergies),
        max_budget_inr=ctx.hard_constraints.max_budget_inr,
        craving_profiles=list(ctx.food_preferences.craving_profiles),
        search_queries=list(ctx.food_preferences.search_queries),
        spice_tolerance=ctx.food_preferences.spice_tolerance,
        state_confidence=ctx.routing.state_confidence,
    )


def get_crisis_response(
    session_id: str,
    turn_count: int,
    ctx: UserContext,
    crisis_kind: str = "self_harm",
) -> ChatTurnResponse:
    safe_ctx = ctx.model_copy(deep=True)
    safe_ctx.turn_count = turn_count
    safe_ctx.routing.next_action = "crisis_support"
    safe_ctx.routing.state_confidence = 1.0
    msg = (
        DISORDERED_EATING_SUPPORT_MESSAGE
        if crisis_kind == "disordered_eating"
        else CRISIS_SUPPORT_MESSAGE
    )
    return ChatTurnResponse(
        session_id=session_id,
        turn_count=turn_count,
        action="crisis_support",
        agent_message=msg,
        user_context=build_context_summary(safe_ctx),
        full_context=safe_ctx,
        recommendations=[],
        quick_reply_pills=[],
        crisis_resources=CRISIS_HELPLINES,
        llm_mode="crisis_guardrail",
    )


def get_harmful_refusal_response(
    session_id: str,
    turn_count: int,
    ctx: UserContext,
) -> ChatTurnResponse:
    safe_ctx = ctx.model_copy(deep=True)
    safe_ctx.turn_count = turn_count
    safe_ctx.routing.next_action = "ask_followup"
    safe_ctx.routing.state_confidence = 1.0
    return ChatTurnResponse(
        session_id=session_id,
        turn_count=turn_count,
        action="ask_followup",
        agent_message=HARMFUL_REFUSAL_MESSAGE,
        user_context=build_context_summary(safe_ctx),
        full_context=safe_ctx,
        recommendations=[],
        quick_reply_pills=["Spicy & crunchy", "Warm comfort bowl", "Light & fresh"],
        crisis_resources=[],
        llm_mode="crisis_guardrail",
    )


def _stricter_diet(prev_diet: Optional[DietaryType], new_diet: Optional[DietaryType]) -> Optional[DietaryType]:
    if not prev_diet or prev_diet == "any":
        return new_diet
    if not new_diet or new_diet == "any":
        return prev_diet
    rank = {"jain": 5, "vegan": 4, "veg": 3, "eggetarian": 2, "halal": 2, "non_veg": 1, "any": 0}
    return new_diet if rank.get(new_diet, 0) >= rank.get(prev_diet, 0) else prev_diet


def merge_and_lock_constraints(
    previous: UserContext,
    proposed: UserContext,
    user_message: str,
    active_filters: Optional[ActiveFilters] = None,
) -> UserContext:
    """Enforce Spec 03 & 07 Rules: Dietary/Allergy persistence and Low-Energy zero-mess + <=30m ETA lock."""
    merged = proposed.model_copy(deep=True)
    merged.session_id = previous.session_id
    merged.turn_count = previous.turn_count

    det_diet, det_allergies, det_excluded = extract_deterministic_safety_constraints(user_message)

    # 1. Dietary lock unless explicitly cancelled by user
    explicit_cancel = bool(CANCEL_VEG_RE.search(user_message))
    if explicit_cancel:
        merged.hard_constraints.dietary_type = proposed.hard_constraints.dietary_type or "any"
    else:
        combined_new = _stricter_diet(proposed.hard_constraints.dietary_type, det_diet)
        merged.hard_constraints.dietary_type = _stricter_diet(
            previous.hard_constraints.dietary_type,
            combined_new,
        )

    # Apply explicit active_filters from UI header toggle (never weakens an existing text dietary lock)
    if active_filters is not None:
        if active_filters.dietary_type is not None and active_filters.dietary_type != "any":
            merged.hard_constraints.dietary_type = _stricter_diet(
                merged.hard_constraints.dietary_type,
                active_filters.dietary_type,
            )
        if active_filters.max_budget_inr is not None:
            merged.hard_constraints.max_budget_inr = active_filters.max_budget_inr

    # 2. Allergy union lock (immutable across session)
    locked_allergies: list[str] = []
    for a in [*previous.hard_constraints.allergies, *proposed.hard_constraints.allergies, *det_allergies]:
        norm = a.strip().lower()
        if norm and norm not in locked_allergies:
            locked_allergies.append(norm)
    merged.hard_constraints.allergies = locked_allergies

    # 3. Excluded ingredients union + medical flags
    medical = detect_medical_flags(user_message)
    extra_markers: list[str] = []
    if medical["diabetic"]:
        extra_markers.append("__diabetic_safe__")
    if medical["pregnant"]:
        extra_markers.append("__pregnancy_safe__")

    locked_excluded: list[str] = []
    for ex in [
        *previous.food_preferences.excluded_ingredients,
        *proposed.food_preferences.excluded_ingredients,
        *det_excluded,
        *extra_markers,
    ]:
        norm = ex.strip().lower()
        if norm and norm not in locked_excluded:
            locked_excluded.append(norm)
    merged.food_preferences.excluded_ingredients = locked_excluded

    # 4. Budget persistence if new turn didn't specify one
    if merged.hard_constraints.max_budget_inr is None and previous.hard_constraints.max_budget_inr is not None:
        merged.hard_constraints.max_budget_inr = previous.hard_constraints.max_budget_inr

    # 5. Spec 03 Rule 4: Tired / Low-Energy automatic rule
    if merged.user_state.energy_level == "low":
        merged.food_preferences.effort_to_eat = "zero_mess"
        merged.hard_constraints.max_eta_mins = min(merged.hard_constraints.max_eta_mins, 30)

    return merged


def verify_zero_hallucinations(
    recommendations: list[ComboRecommendation],
    catalog: CatalogRepository,
    context: UserContext,
) -> list[ComboRecommendation]:
    """Deterministic post-check ensuring zero hallucinated dishes, prices, or constraint violations."""
    verified: list[ComboRecommendation] = []
    for combo in recommendations:
        rest = catalog.get_restaurant(combo.restaurant.id)
        if rest is None or not rest.is_open:
            continue
        if combo.restaurant.eta_mins > context.hard_constraints.max_eta_mins:
            continue

        valid_items = True
        price_sum = 0
        for c_item in combo.items:
            db_item = catalog.get_item(c_item.item_id)
            if db_item is None or not db_item.is_available:
                valid_items = False
                break
            if db_item.restaurant_id != rest.id:
                valid_items = False
                break
            if not item_matches_dietary(db_item, context.hard_constraints.dietary_type):
                valid_items = False
                break
            if not item_is_allergy_safe(
                db_item,
                context.hard_constraints.allergies,
                context.food_preferences.excluded_ingredients,
            ):
                valid_items = False
                break
            price_sum += db_item.price_inr

        if not valid_items:
            continue
        if price_sum != combo.total_price_inr:
            continue
        if context.hard_constraints.max_budget_inr is not None and price_sum > context.hard_constraints.max_budget_inr:
            continue
        verified.append(combo)

    return verified


def sanitize_reply_and_pills(
    reply_text: str,
    pills: list[str],
    *,
    enforce_45_word_limit: bool = True,
) -> tuple[str, list[str]]:
    clean_text = " ".join(reply_text.strip().split())
    if LEAK_GUARD_RE.search(clean_text):
        clean_text = "I'm MoodBite—here strictly to help sort out fast food that fits your vibe. Tell me what you're craving!"
    if SHAMING_WORDS_RE.search(clean_text):
        clean_text = SHAMING_WORDS_RE.sub("rich", clean_text)

    if enforce_45_word_limit:
        words = clean_text.split()
        if len(words) > 44:
            clean_text = " ".join(words[:43]).rstrip(",;:") + "..."

    clean_pills: list[str] = []
    for pill in pills:
        p = " ".join(pill.strip().split())
        if not p:
            continue
        p_words = p.split()
        if len(p_words) > 4:
            p = " ".join(p_words[:4])
        if p not in clean_pills:
            clean_pills.append(p)
        if len(clean_pills) >= 4:
            break

    while len(clean_pills) < 3:
        fallback_defaults = ["Drained & tired", "Stressed, want spicy", "Light & fresh", "Surprise me"]
        for cand in fallback_defaults:
            if cand not in clean_pills:
                clean_pills.append(cand)
                break

    return clean_text, clean_pills[:4]
