"""Pydantic v2 state and LLM extraction schemas matching Spec 03."""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field

DietaryType = Literal["veg", "jain", "vegan", "eggetarian", "halal", "non_veg", "any"]
EnergyLevel = Literal["low", "medium", "high"]
StressLevel = Literal["low", "medium", "high"]
SpiceTolerance = Literal["mild", "medium", "high"]
EffortToEat = Literal["zero_mess", "standard"]
PortionSize = Literal["light_snack", "regular_meal", "hearty_feast"]
NextAction = Literal["ask_followup", "recommend_combos", "crisis_support"]


class UserState(BaseModel):
    primary_mood: str = "neutral_hungry"
    emotional_valence: float = Field(default=0.0, ge=-1.0, le=1.0)
    energy_level: EnergyLevel = "medium"
    stress_level: StressLevel = "low"
    goal: str = "satisfying_meal"


class FoodPreferences(BaseModel):
    craving_profiles: list[str] = Field(default_factory=list)
    search_queries: list[str] = Field(default_factory=list)
    spice_tolerance: SpiceTolerance = "medium"
    effort_to_eat: EffortToEat = "standard"
    portion_size: PortionSize = "regular_meal"
    excluded_ingredients: list[str] = Field(default_factory=list)


class HardConstraints(BaseModel):
    dietary_type: Optional[DietaryType] = None
    allergies: list[str] = Field(default_factory=list)
    max_budget_inr: Optional[int] = Field(default=None, ge=50, le=5000)
    max_eta_mins: int = Field(default=35, ge=10, le=90)


class RoutingState(BaseModel):
    state_confidence: float = Field(default=0.3, ge=0.0, le=1.0)
    next_action: NextAction = "ask_followup"
    clarifying_question: Optional[str] = None


class UserContext(BaseModel):
    session_id: str
    turn_count: int = Field(default=0, ge=0)
    user_state: UserState = Field(default_factory=UserState)
    food_preferences: FoodPreferences = Field(default_factory=FoodPreferences)
    hard_constraints: HardConstraints = Field(default_factory=HardConstraints)
    routing: RoutingState = Field(default_factory=RoutingState)


class LLMExtractionOutput(BaseModel):
    """Strict structured JSON schema required from every LLM turn."""

    updated_context: UserContext
    reply_text: str = Field(..., min_length=1, max_length=600)
    quick_reply_pills: list[str] = Field(default_factory=list, max_length=4)
