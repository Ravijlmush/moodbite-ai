"""Seed PostgreSQL + pgvector with restaurants, menu items, and 384-dim embeddings."""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

import asyncpg

ROOT_DIR = Path(__file__).resolve().parent.parent
BACKEND_DIR = ROOT_DIR / "backend"
sys.path.insert(0, str(BACKEND_DIR))

from app.config import get_settings
from app.recommender.embeddings import EmbeddingService
from app.schemas.catalog import MenuItem


async def seed() -> None:
    settings = get_settings()
    if not settings.database_url:
        raise SystemExit("DATABASE_URL is not configured in .env. Set it before running db/seed_postgres.py.")

    catalog_file = Path(settings.catalog_path)
    data = json.loads(catalog_file.read_text(encoding="utf-8"))
    restaurants = data["restaurants"]
    menu_items = data["menu_items"]
    embedder = EmbeddingService(provider="local_semantic")

    conn = await asyncpg.connect(settings.database_url)
    try:
        async with conn.transaction():
            for rest in restaurants:
                await conn.execute(
                    """
                    INSERT INTO restaurants (id, name, rating, lat, lng, base_prep_mins, is_open)
                    VALUES ($1, $2, $3, $4, $5, $6, $7)
                    ON CONFLICT (id) DO UPDATE SET
                        name = EXCLUDED.name,
                        rating = EXCLUDED.rating,
                        lat = EXCLUDED.lat,
                        lng = EXCLUDED.lng,
                        base_prep_mins = EXCLUDED.base_prep_mins,
                        is_open = EXCLUDED.is_open
                    """,
                    rest["id"],
                    rest["name"],
                    rest["rating"],
                    rest["lat"],
                    rest["lng"],
                    rest["base_prep_mins"],
                    rest["is_open"],
                )

            for raw_item in menu_items:
                item = MenuItem.model_validate(raw_item)
                vec = embedder.embed_item(item)
                vec_str = "[" + ",".join(f"{x:.6f}" for x in vec) + "]"
                await conn.execute(
                    """
                    INSERT INTO menu_items (
                        id, restaurant_id, name, category, dietary_type, dietary_tags,
                        allergens, price_inr, prep_time_mins, mood_tags, sensory_tags,
                        effort_to_eat, dopamine_score, heavy_index, pairing_affinities,
                        mood_embedding, is_available
                    )
                    VALUES (
                        $1, $2, $3, $4, $5, $6,
                        $7, $8, $9, $10, $11,
                        $12, $13, $14, $15,
                        $16::vector, $17
                    )
                    ON CONFLICT (id) DO UPDATE SET
                        name = EXCLUDED.name,
                        price_inr = EXCLUDED.price_inr,
                        mood_tags = EXCLUDED.mood_tags,
                        sensory_tags = EXCLUDED.sensory_tags,
                        mood_embedding = EXCLUDED.mood_embedding,
                        is_available = EXCLUDED.is_available
                    """,
                    item.id,
                    item.restaurant_id,
                    item.name,
                    item.category,
                    item.dietary_type,
                    item.dietary_tags,
                    item.allergens,
                    item.price_inr,
                    item.prep_time_mins,
                    item.mood_tags,
                    item.sensory_tags,
                    item.effort_to_eat,
                    item.dopamine_score,
                    item.heavy_index,
                    item.pairing_affinities,
                    vec_str,
                    item.is_available,
                )
        print(f"Seeded {len(restaurants)} restaurants and {len(menu_items)} items into PostgreSQL.")
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(seed())
