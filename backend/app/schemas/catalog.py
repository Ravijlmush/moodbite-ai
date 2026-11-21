"""Catalog and combo recommendation Pydantic v2 models (Specs 04 & 06)."""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field

ItemCategory = Literal[
    "main_bowl",
    "roll_wrap",
    "biryani_rice",
    "noodle_soup",
    "comfort_plate",
    "beverage",
    "dessert",
]
CatalogDietaryType = Literal["veg", "egg", "non_veg"]
CatalogEffort = Literal["zero_mess", "standard"]


class Restaurant(BaseModel):
    id: str
    name: str
    rating: float = Field(..., ge=1.0, le=5.0)
    lat: float
    lng: float
    base_prep_mins: int = Field(..., ge=1, le=90)
    is_open: bool = True


class MenuItem(BaseModel):
    id: str
    restaurant_id: str
    name: str
    category: ItemCategory
    dietary_type: CatalogDietaryType
    dietary_tags: list[str] = Field(default_factory=list)
    allergens: list[str] = Field(default_factory=list)
    price_inr: int = Field(..., ge=1)
    prep_time_mins: int = Field(default=12, ge=1, le=60)
    mood_tags: list[str] = Field(default_factory=list)
    sensory_tags: list[str] = Field(default_factory=list)
    effort_to_eat: CatalogEffort = "zero_mess"
    dopamine_score: float = Field(default=0.75, ge=0.0, le=1.0)
    heavy_index: float = Field(default=0.5, ge=0.0, le=1.0)
    pairing_affinities: list[str] = Field(default_factory=list)
    is_available: bool = True


class ComboItem(BaseModel):
    item_id: str
    name: str
    price_inr: int
    dietary_type: CatalogDietaryType = "veg"
    category: str = "main_bowl"


class ComboRestaurant(BaseModel):
    id: str
    name: str
    rating: float
    eta_mins: int


class ComboRecommendation(BaseModel):
    combo_id: str
    mood_badge: str
    title: str
    restaurant: ComboRestaurant
    items: list[ComboItem]
    total_price_inr: int
    why_it_fits: str
    match_score: float = Field(..., ge=0.0, le=1.0)
    dietary_type: CatalogDietaryType = "veg"
    coupon_badge: Optional[str] = None
    source: Literal["swiggy_mcp_live", "demo_fallback"] = "demo_fallback"
