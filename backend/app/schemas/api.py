"""REST and SSE API request/response Pydantic v2 models (Spec 06)."""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator

from app.schemas.catalog import ComboRecommendation
from app.schemas.context import DietaryType, EffortToEat, EnergyLevel, NextAction, UserContext


class Location(BaseModel):
    lat: float = 28.6139
    lng: float = 77.2090


class ActiveFilters(BaseModel):
    dietary_type: Optional[DietaryType] = None
    max_budget_inr: Optional[int] = Field(default=None, ge=50, le=5000)


class ChatTurnRequest(BaseModel):
    session_id: str = Field(..., min_length=1, max_length=128)
    user_id: str = Field(default="usr_guest", min_length=1, max_length=128)
    message: str = Field(default="")
    location: Location = Field(default_factory=Location)
    active_filters: ActiveFilters = Field(default_factory=ActiveFilters)
    swiggy_access_token: Optional[str] = None
    address_id: Optional[str] = None

    @field_validator("message", mode="before")
    @classmethod
    def normalize_and_bound_message(cls, value: object) -> str:
        if value is None:
            return ""
        text = str(value)
        if len(text) > 1200:
            return f"{text[:900]} ... {text[-200:]}"
        return text


class ChatRefineRequest(BaseModel):
    session_id: str = Field(..., min_length=1, max_length=128)
    user_id: str = Field(default="usr_guest", min_length=1, max_length=128)
    chip: str = Field(..., min_length=1, max_length=80)
    location: Location = Field(default_factory=Location)
    active_filters: Optional[ActiveFilters] = None
    swiggy_access_token: Optional[str] = None
    address_id: Optional[str] = None


class UserContextSummary(BaseModel):
    primary_mood: str
    energy_level: EnergyLevel
    effort_to_eat: EffortToEat
    max_eta_mins: int
    dietary_type: Optional[DietaryType] = None
    allergies: list[str] = Field(default_factory=list)
    max_budget_inr: Optional[int] = None
    craving_profiles: list[str] = Field(default_factory=list)
    search_queries: list[str] = Field(default_factory=list)
    spice_tolerance: str = "medium"
    state_confidence: float = 0.0


class CrisisResource(BaseModel):
    name: str
    contact: str
    availability: str
    region: str


class ChatTurnResponse(BaseModel):
    session_id: str
    turn_count: int
    action: NextAction
    agent_message: str
    user_context: UserContextSummary
    full_context: UserContext
    recommendations: list[ComboRecommendation] = Field(default_factory=list)
    quick_reply_pills: list[str] = Field(default_factory=list)
    crisis_resources: list[CrisisResource] = Field(default_factory=list)
    latency_ms: float = 0.0
    llm_mode: Literal["openrouter", "openai", "gemini", "ollama", "offline", "deterministic_fallback", "crisis_guardrail"] = "offline"
    catalog_source: Literal["swiggy_mcp_live", "demo_fallback"] = "demo_fallback"


class AddToCartRequest(BaseModel):
    session_id: str = Field(..., min_length=1, max_length=128)
    combo_id: str = Field(..., min_length=1, max_length=128)
    quantity: int = Field(default=1, ge=1, le=20)
    combo: Optional[ComboRecommendation] = None


class AddComboToSwiggyCartRequest(BaseModel):
    session_id: str = Field(..., min_length=1, max_length=128)
    restaurant_id: str = Field(..., min_length=1, max_length=128)
    item_ids: list[str] = Field(..., min_length=1)
    combo_id: Optional[str] = None
    combo: Optional[ComboRecommendation] = None
    address_id: Optional[str] = None
    swiggy_access_token: Optional[str] = None


class CartEntry(BaseModel):
    combo: ComboRecommendation
    quantity: int = 1
    line_total_inr: int


class CartResponse(BaseModel):
    session_id: str
    items: list[CartEntry] = Field(default_factory=list)
    total_items: int = 0
    total_price_inr: int = 0
    swiggy_synced: bool = False
    swiggy_message: Optional[str] = None


class SessionDetailResponse(BaseModel):
    session_id: str
    turn_count: int
    user_context: UserContext
    chat_history: list[dict[str, str]] = Field(default_factory=list)
    recommendations: list[ComboRecommendation] = Field(default_factory=list)
    cart: CartResponse


class HealthResponse(BaseModel):
    status: str = "ok"
    app: str
    version: str
    llm_provider: str
    catalog_restaurants: int
    catalog_items: int
    storage_backend: str
    catalog_backend: str
    daily_request_limit: int = 20
    daily_requests_used: int = 0
    daily_requests_remaining: int = 20
    swiggy_mcp_connected: bool = False
    swiggy_mcp_url: str = "https://mcp.swiggy.com/food"


class SwiggyAddress(BaseModel):
    address_id: str
    label: str = "Saved Address"
    address_line: str = ""
    lat: Optional[float] = None
    lng: Optional[float] = None


class SwiggyAuthStatusResponse(BaseModel):
    connected: bool
    mcp_url: str
    demo_fallback_mode: bool
    selected_address_id: Optional[str] = None
    addresses: list[SwiggyAddress] = Field(default_factory=list)


class SwiggyTokenConnectRequest(BaseModel):
    access_token: str = Field(..., min_length=4)
    address_id: Optional[str] = None


class CatalogStatsResponse(BaseModel):
    total_restaurants: int
    open_restaurants: int
    total_items: int
    main_dishes: int
    boosters: int
    veg_items: int
    jain_items: int
    vegan_items: int
    non_veg_items: int
    egg_items: int
