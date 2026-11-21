"""Catalog repositories: Local JSON (with precomputed 384-dim embeddings) & PostgreSQL/pgvector."""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Protocol

from app.recommender.embeddings import EmbeddingService
from app.schemas.api import CatalogStatsResponse, Location
from app.schemas.catalog import MenuItem, Restaurant

CITY_HUB_LAT = 28.6139
CITY_HUB_LNG = 77.2090


def haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    r = 6371.0
    d_lat = math.radians(lat2 - lat1)
    d_lng = math.radians(lng2 - lng1)
    a = (
        math.sin(d_lat / 2) ** 2
        + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(d_lng / 2) ** 2
    )
    return 2 * r * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def compute_live_eta_mins(restaurant: Restaurant, location: Location) -> int:
    dist_from_hub = haversine_km(location.lat, location.lng, CITY_HUB_LAT, CITY_HUB_LNG)
    # If caller sends browser coordinates from another city, map to demo city hub so local catalog remains serviceable
    eff_lat = location.lat if dist_from_hub <= 35.0 else CITY_HUB_LAT
    eff_lng = location.lng if dist_from_hub <= 35.0 else CITY_HUB_LNG
    dist_km = haversine_km(eff_lat, eff_lng, restaurant.lat, restaurant.lng)
    rider_mins = max(6, round(dist_km * 3.0))
    return restaurant.base_prep_mins + rider_mins


class CatalogRepository(Protocol):
    backend_name: str

    def list_restaurants(self) -> list[Restaurant]: ...
    def get_restaurant(self, restaurant_id: str) -> Restaurant | None: ...
    def list_items(self) -> list[MenuItem]: ...
    def get_item(self, item_id: str) -> MenuItem | None: ...
    def get_item_embedding(self, item_id: str) -> list[float]: ...
    def get_stats(self) -> CatalogStatsResponse: ...


class LocalJsonCatalogRepository:
    """In-memory repository backed by backend/data/catalog.json with precomputed 384-dim embeddings."""

    backend_name: str = "local_json_semantic"

    def __init__(self, catalog_path: str | Path, embedder: EmbeddingService | None = None) -> None:
        self.catalog_path = Path(catalog_path)
        self.embedder = embedder or EmbeddingService()
        raw = json.loads(self.catalog_path.read_text(encoding="utf-8"))
        self._restaurants: dict[str, Restaurant] = {}
        self._items: dict[str, MenuItem] = {}
        self._embeddings: dict[str, list[float]] = {}

        for r_data in raw.get("restaurants", []):
            r = Restaurant.model_validate(r_data)
            self._restaurants[r.id] = r

        for i_data in raw.get("menu_items", []):
            item = MenuItem.model_validate(i_data)
            self._items[item.id] = item
            self._embeddings[item.id] = self.embedder.embed_item(item)

    def list_restaurants(self) -> list[Restaurant]:
        return list(self._restaurants.values())

    def get_restaurant(self, restaurant_id: str) -> Restaurant | None:
        return self._restaurants.get(restaurant_id)

    def list_items(self) -> list[MenuItem]:
        return list(self._items.values())

    def get_item(self, item_id: str) -> MenuItem | None:
        return self._items.get(item_id)

    def get_item_embedding(self, item_id: str) -> list[float]:
        return self._embeddings.get(item_id, [0.0] * 384)

    def get_stats(self) -> CatalogStatsResponse:
        items = list(self._items.values())
        restaurants = list(self._restaurants.values())
        return CatalogStatsResponse(
            total_restaurants=len(restaurants),
            open_restaurants=sum(1 for r in restaurants if r.is_open),
            total_items=len(items),
            main_dishes=sum(1 for i in items if i.category not in ("beverage", "dessert")),
            boosters=sum(1 for i in items if i.category in ("beverage", "dessert")),
            veg_items=sum(1 for i in items if i.dietary_type == "veg"),
            jain_items=sum(1 for i in items if "jain" in i.dietary_tags),
            vegan_items=sum(1 for i in items if "vegan" in i.dietary_tags),
            non_veg_items=sum(1 for i in items if i.dietary_type == "non_veg"),
            egg_items=sum(1 for i in items if i.dietary_type == "egg"),
        )


class PostgresPgVectorCatalogRepository(LocalJsonCatalogRepository):
    """PostgreSQL + pgvector repository with local JSON mirror fallback if DB is unreachable."""

    def __init__(self, database_url: str, catalog_path: str | Path, embedder: EmbeddingService | None = None) -> None:
        super().__init__(catalog_path=catalog_path, embedder=embedder)
        self.database_url = database_url
        self.backend_name = "postgres_pgvector_ready"

    async def query_top_mains_pgvector(
        self,
        query_vec: list[float],
        dietary_type: str | None,
        limit: int = 25,
    ) -> list[tuple[str, float]]:
        import asyncpg

        vec_literal = "[" + ",".join(f"{x:.6f}" for x in query_vec) + "]"
        conn = await asyncpg.connect(self.database_url)
        try:
            where = "WHERE m.is_available = TRUE AND r.is_open = TRUE AND m.category NOT IN ('beverage', 'dessert')"
            params: list[object] = [vec_literal, limit]
            if dietary_type == "veg":
                where += " AND m.dietary_type = 'veg'"
            elif dietary_type == "jain":
                where += " AND m.dietary_type = 'veg' AND 'jain' = ANY(m.dietary_tags)"
            elif dietary_type == "vegan":
                where += " AND m.dietary_type = 'veg' AND 'vegan' = ANY(m.dietary_tags)"
            elif dietary_type == "eggetarian":
                where += " AND m.dietary_type IN ('veg', 'egg')"
            rows = await conn.fetch(
                f"""
                SELECT m.id, 1 - (m.mood_embedding <=> $1::vector) AS similarity
                FROM menu_items m
                JOIN restaurants r ON r.id = m.restaurant_id
                {where}
                ORDER BY m.mood_embedding <=> $1::vector ASC
                LIMIT $2
                """,
                *params,
            )
            return [(row["id"], float(row["similarity"])) for row in rows]
        finally:
            await conn.close()
