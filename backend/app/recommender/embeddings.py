"""384-dimensional semantic mood-food embedding generator (pgvector vector(384) compatible)."""

from __future__ import annotations

import hashlib
import math
import re
from typing import Iterable

import httpx

from app.schemas.catalog import MenuItem
from app.schemas.context import UserContext

EMBEDDING_DIM = 384
CONCEPT_DIM = 96

# Structured semantic concept buckets mapped to slots 0..95
CONCEPT_BUCKETS: list[tuple[int, float, tuple[str, ...]]] = [
    (0, 2.2, ("tired", "drained", "exhausted", "fatigued", "low_energy", "tired_and_down", "sleepy", "burnout", "burned_out", "late_night")),
    (1, 2.2, ("comfort", "comfort_classic", "warm_comfort", "homestyle", "homely", "cozy", "soul_food", "rajma", "khichdi", "dal", "curd_rice")),
    (2, 2.0, ("nostalgic", "mom", "childhood", "ghar", "classic", "familiar", "traditional")),
    (3, 2.0, ("cheer_up", "mood_off", "down", "sad", "low_mood", "heartbroken", "heartbroken_low", "upset", "blue", "dopamine", "comfort_and_cheer_up")),
    (4, 2.1, ("stressed", "stressed_angry", "angry", "frustrated", "overwhelmed", "tense", "awful", "meeting", "exam", "pre_exam", "deadline")),
    (5, 2.1, ("spicy", "bold_spicy", "fiery", "chilli", "tikka", "schezwan", "tandoori", "masala", "peri_peri", "pepper", "zing")),
    (6, 2.0, ("crunchy", "crispy", "sensory_release", "crunch", "roll", "wrap", "noodles", "samosa", "fried", "crisp")),
    (7, 2.2, ("sluggish", "sluggish_heavy", "heavy", "post_illness", "fever", "post_fever", "sick", "recovering", "upset_stomach", "queasy")),
    (8, 2.2, ("light", "light_comfort", "gentle", "easy_to_digest", "curd", "soup", "clear", "poha", "idli", "moong", "steamed", "broth")),
    (9, 2.0, ("fresh", "refreshing", "cooling", "lemonade", "chaas", "lime", "mint", "cucumber", "salad", "cooler")),
    (10, 2.1, ("celebratory", "celebratory_happy", "celebrate", "happy", "party", "weekend", "treat", "indulgent", "reward", "fun", "chill")),
    (11, 2.0, ("sweet", "sweet_treat", "dessert", "chocolate", "choco", "gulab_jamun", "brownie", "lava", "ice_cream", "kheer", "halwa", "shake")),
    (12, 1.8, ("fizzy", "fizzy_sweet_kick", "coke", "cola", "limca", "soda", "thums_up", "fizz", "chilled", "sparkling")),
    (13, 1.9, ("zero_mess", "no_mess", "bowl", "one_hand", "spoon", "easy_to_eat", "effortless", "desk", "laptop", "coding")),
    (14, 1.5, ("standard", "plate", "feast", "thali", "paratha", "naan", "shareable")),
    (15, 1.8, ("warm", "hot", "steaming", "soothing", "simmered")),
    (16, 1.7, ("hearty", "filling", "protein", "rich", "creamy", "makhani", "butter", "biryani", "paneer", "chicken")),
    (17, 1.6, ("caffeine", "coffee", "chai", "tea", "wake_up", "cold_coffee", "ginger_tea", "espresso", "focus")),
    (18, 1.5, ("bored", "bored_restless", "surprise", "fusion", "tangy", "street", "chatpata", "korean", "teriyaki", "momos")),
    (19, 1.6, ("budget", "cheap", "affordable", "value", "pocket", "quick_bite")),
]

TOKEN_RE = re.compile(r"[a-z0-9_]+")


def _tokenize(text: str) -> list[str]:
    cleaned = text.lower().replace("-", "_").replace("+", " ")
    raw = TOKEN_RE.findall(cleaned)
    tokens: list[str] = []
    for tok in raw:
        tokens.append(tok)
        if "_" in tok:
            tokens.extend(part for part in tok.split("_") if len(part) >= 2)
    return tokens


def _normalize(vec: list[float]) -> list[float]:
    norm = math.sqrt(sum(v * v for v in vec))
    if norm <= 1e-12:
        return [0.0] * len(vec)
    return [v / norm for v in vec]


def cosine_similarity(a: list[float], b: list[float]) -> float:
    if len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    # Clamp cosine to [0, 1] for scoring
    return max(0.0, min(1.0, (dot + 1.0) / 2.0 if dot < 0 else dot))


class EmbeddingService:
    """Produces 384-dimensional normalized mood/food semantic vectors."""

    def __init__(self, provider: str = "local_semantic", openai_api_key: str = "", openai_base_url: str = "https://api.openai.com/v1") -> None:
        self.provider = provider
        self.openai_api_key = openai_api_key
        self.openai_base_url = openai_base_url.rstrip("/")

    def embed_text_local(self, text: str) -> list[float]:
        vec = [0.0] * EMBEDDING_DIM
        tokens = _tokenize(text)
        token_set = set(tokens)
        lowered = text.lower()

        # 1. Semantic concept bucket projections
        for slot, weight, keywords in CONCEPT_BUCKETS:
            hits = 0
            for kw in keywords:
                if kw in token_set or kw in lowered:
                    hits += 1
            if hits > 0:
                boost = weight * (1.0 + 0.25 * min(hits - 1, 3))
                vec[slot] += boost
                vec[(slot * 3 + 21) % CONCEPT_DIM] += boost * 0.65

        # 2. Hashed lexical unigrams + bigrams into slots 96..383
        hash_span = EMBEDDING_DIM - CONCEPT_DIM
        for idx, tok in enumerate(tokens):
            digest = hashlib.blake2b(tok.encode("utf-8"), digest_size=8).digest()
            bucket = CONCEPT_DIM + (int.from_bytes(digest[:4], "little") % hash_span)
            sign = 1.0 if (digest[4] & 1) == 0 else -1.0
            vec[bucket] += sign * 0.85

            if idx + 1 < len(tokens):
                bigram = f"{tok}__{tokens[idx + 1]}"
                bdigest = hashlib.blake2b(bigram.encode("utf-8"), digest_size=8).digest()
                bbucket = CONCEPT_DIM + (int.from_bytes(bdigest[:4], "little") % hash_span)
                bsign = 1.0 if (bdigest[4] & 1) == 0 else -1.0
                vec[bbucket] += bsign * 0.55

        return _normalize(vec)

    def embed_item(self, item: MenuItem) -> list[float]:
        parts: list[str] = [
            item.name,
            item.category,
            item.effort_to_eat,
            *item.mood_tags,
            *item.sensory_tags,
            *item.dietary_tags,
        ]
        if item.heavy_index <= 0.35:
            parts.extend(["light", "easy_to_digest", "gentle"])
        elif item.heavy_index >= 0.72:
            parts.extend(["hearty", "filling", "rich"])
        if item.dopamine_score >= 0.82:
            parts.extend(["cheer_up", "dopamine", "comfort"])
        return self.embed_text_local(" ".join(parts))

    def embed_user_context(self, ctx: UserContext, user_message: str = "") -> list[float]:
        parts: list[str] = [
            ctx.user_state.primary_mood,
            ctx.user_state.goal,
            f"{ctx.user_state.energy_level}_energy",
            f"{ctx.user_state.stress_level}_stress",
            ctx.food_preferences.effort_to_eat,
            ctx.food_preferences.spice_tolerance,
            ctx.food_preferences.portion_size,
            *ctx.food_preferences.craving_profiles,
        ]
        if ctx.user_state.energy_level == "low":
            parts.extend(["tired", "zero_mess", "comfort", "warm", "fast"])
        if ctx.user_state.stress_level == "high":
            parts.extend(["stressed", "spicy", "crunchy", "sensory_release"])
        if ctx.food_preferences.spice_tolerance == "high":
            parts.extend(["spicy", "bold_spicy", "fiery"])
        if user_message:
            parts.append(user_message)
        return self.embed_text_local(" ".join(parts))

    async def embed_query(self, text: str) -> list[float]:
        if self.provider == "openai" and self.openai_api_key.strip():
            try:
                async with httpx.AsyncClient(timeout=2.0) as client:
                    resp = await client.post(
                        f"{self.openai_base_url}/embeddings",
                        headers={"Authorization": f"Bearer {self.openai_api_key.strip()}"},
                        json={
                            "model": "text-embedding-3-small",
                            "input": text,
                            "dimensions": EMBEDDING_DIM,
                        },
                    )
                    resp.raise_for_status()
                    data = resp.json()
                    emb = data["data"][0]["embedding"]
                    if isinstance(emb, list) and len(emb) == EMBEDDING_DIM:
                        return _normalize([float(x) for x in emb])
            except Exception:
                pass
        return self.embed_text_local(text)

    @staticmethod
    def batch_embed_texts(texts: Iterable[str]) -> list[list[float]]:
        svc = EmbeddingService()
        return [svc.embed_text_local(t) for t in texts]
