"""Deterministic safety, dietary lock, crisis, brevity, and zero-hallucination guardrails (Spec 07)."""

from __future__ import annotations

import re
from typing import Optional

from app.prompts.templates import CRISIS_HELPLINES, CRISIS_SUPPORT_MESSAGE
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

# High-precision crisis phrases
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

# Explicit user cancellation of an earlier dietary lock
CANCEL_VEG_RE = re.compile(
    r"\b(?:non[\s-]?veg\s+(?:is\s+fine|okay|ok|works)|eat\s+(?:meat|chicken|anything)|remove\s+veg|no\s+diet\s+restriction|all\s+meat)\b",
    re.IGNORECASE,
)

SHAMING_WORDS_RE = re.compile(
    r"\b(?:unhealthy|junk\s+food|too\s+much\s+sugar|high\s+calories|guilty\s+pleasure|bad\s+for\s+you|weight\s+gain)\b",
    re.IGNORECASE,
)


def detect_crisis(message: str) -> bool:
    if not message:
        return False
    stripped = HUNGER_IDIOM_RE.sub("", message)
    return bool(CRISIS_RE.search(stripped))


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
        spice_tolerance=ctx.food_preferences.spice_tolerance,
        state_confidence=ctx.routing.state_confidence,
    )


def get_crisis_response(session_id: str, turn_count: int, ctx: UserContext) -> ChatTurnResponse:
    safe_ctx = ctx.model_copy(deep=True)
    safe_ctx.turn_count = turn_count
    safe_ctx.routing.next_action = "crisis_support"
    safe_ctx.routing.state_confidence = 1.0
    return ChatTurnResponse(
        session_id=session_id,
        turn_count=turn_count,
        action="crisis_support",
        agent_message=CRISIS_SUPPORT_MESSAGE,
        user_context=build_context_summary(safe_ctx),
        full_context=safe_ctx,
        recommendations=[],
        quick_reply_pills=[],
        crisis_resources=CRISIS_HELPLINES,
        llm_mode="crisis_guardrail",
    )


def _stricter_diet(prev_diet: Optional[DietaryType], new_diet: Optional[DietaryType]) -> Optional[DietaryType]:
    if not prev_diet or prev_diet == "any":
        return new_diet
    if not new_diet or new_diet == "any":
        return prev_diet
    # Preserve stricter constraint unless explicitly cancelled
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

    # 1. Dietary lock unless explicitly cancelled by user or header filter
    explicit_cancel = bool(CANCEL_VEG_RE.search(user_message))
    if explicit_cancel:
        merged.hard_constraints.dietary_type = proposed.hard_constraints.dietary_type or "any"
    else:
        merged.hard_constraints.dietary_type = _stricter_diet(
            previous.hard_constraints.dietary_type,
            proposed.hard_constraints.dietary_type,
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
    for a in [*previous.hard_constraints.allergies, *proposed.hard_constraints.allergies]:
        norm = a.strip().lower()
        if norm and norm not in locked_allergies:
            locked_allergies.append(norm)
    merged.hard_constraints.allergies = locked_allergies

    # 3. Excluded ingredients union
    locked_excluded: list[str] = []
    for ex in [*previous.food_preferences.excluded_ingredients, *proposed.food_preferences.excluded_ingredients]:
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
