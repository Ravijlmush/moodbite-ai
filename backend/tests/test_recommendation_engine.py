"""Deterministic recommendation engine, scoring formula, refinement, and latency tests."""

from __future__ import annotations

import time

from app.config import Settings
from app.recommender.catalog_repo import LocalJsonCatalogRepository
from app.recommender.engine import RecommendationEngine
from app.recommender.refiner import apply_refinement_chip
from app.schemas.api import Location
from app.schemas.context import FoodPreferences, HardConstraints, UserContext, UserState


def _build_engine() -> tuple[LocalJsonCatalogRepository, RecommendationEngine]:
    settings = Settings(llm_provider="offline")
    repo = LocalJsonCatalogRepository(settings.catalog_path)
    return repo, RecommendationEngine(catalog=repo)


def test_catalog_minimums() -> None:
    repo, _ = _build_engine()
    stats = repo.get_stats()
    assert stats.total_restaurants >= 20
    assert stats.total_items >= 150
    assert stats.main_dishes >= 70
    assert stats.boosters >= 50
    assert stats.jain_items >= 10
    assert stats.vegan_items >= 15


def test_excludes_closed_and_slow_restaurants() -> None:
    _, engine = _build_engine()
    ctx = UserContext(
        session_id="eng_01",
        turn_count=1,
        user_state=UserState(primary_mood="tired_and_down", energy_level="low"),
        food_preferences=FoodPreferences(
            craving_profiles=["comfort_classic", "warm_comfort"],
            effort_to_eat="zero_mess",
        ),
        hard_constraints=HardConstraints(dietary_type="veg", max_eta_mins=30),
    )
    recs = engine.recommend(ctx, Location(), limit=5)
    assert len(recs) >= 3
    rest_ids = [r.restaurant.id for r in recs]
    assert "rest_991" not in rest_ids  # slow restaurant excluded
    assert "rest_992" not in rest_ids  # closed restaurant excluded
    assert len(set(rest_ids)) == len(rest_ids)  # max 1 combo per restaurant
    # Distinct main dish archetypes prioritized
    categories = [r.items[0].category for r in recs]
    assert len(set(categories)) >= 2


def test_scoring_formula_components() -> None:
    repo, engine = _build_engine()
    rest = repo.get_restaurant("rest_882")
    main = repo.get_item("dish_10492")
    booster = repo.get_item("bev_201")
    assert rest and main and booster

    ctx = UserContext(
        session_id="eng_score",
        turn_count=1,
        user_state=UserState(primary_mood="tired_and_down", energy_level="low"),
        food_preferences=FoodPreferences(effort_to_eat="zero_mess"),
        hard_constraints=HardConstraints(max_eta_mins=30),
    )
    score = engine._compute_combo_score(
        main=main,
        booster=booster,
        restaurant=rest,
        eta_mins=22,
        main_mood_score=0.90,
        affinity_score=1.0,
        context=ctx,
    )
    expected = (
        0.40 * 0.90
        + 0.25 * (1.0 - 22 / 45.0)
        + 0.15 * 1.0
        + 0.10 * ((4.4 - 3.0) / 2.0)
        + 0.10 * 1.0
    )
    assert abs(score - round(expected, 4)) < 1e-4


def test_refinement_chips_and_swap_drink() -> None:
    _, engine = _build_engine()
    ctx = UserContext(
        session_id="eng_ref",
        turn_count=1,
        user_state=UserState(primary_mood="tired_and_down", energy_level="low"),
        food_preferences=FoodPreferences(craving_profiles=["warm_comfort"], effort_to_eat="zero_mess"),
        hard_constraints=HardConstraints(dietary_type="veg", max_eta_mins=30),
    )
    base_recs = engine.recommend(ctx, Location(), limit=4, swap_drink_step=0)
    assert len(base_recs) >= 3

    # Under ₹200 budget chip
    c200, step, _ = apply_refinement_chip(ctx, "Under ₹200", 0)
    r200 = engine.recommend(c200, Location(), limit=4, swap_drink_step=step)
    assert len(r200) >= 3
    assert all(r.total_price_inr <= 200 for r in r200)

    # Swap drink rotates booster while keeping same restaurant pairing valid
    cswap, step2, _ = apply_refinement_chip(ctx, "Swap drink", 0)
    assert step2 == 1
    rswap = engine.recommend(cswap, Location(), limit=4, swap_drink_step=step2)
    assert len(rswap) >= 3
    base_boosters = {r.restaurant.id: r.items[1].item_id for r in base_recs}
    changed = sum(
        1 for r in rswap if r.restaurant.id in base_boosters and r.items[1].item_id != base_boosters[r.restaurant.id]
    )
    assert changed >= 1


def test_engine_p99_latency_under_120ms() -> None:
    """Spec 08 Performance Benchmark: P99 Recommendation Engine Query Time < 120 ms."""
    _, engine = _build_engine()
    ctx = UserContext(
        session_id="eng_perf",
        turn_count=1,
        user_state=UserState(primary_mood="tired_and_down", energy_level="low"),
        food_preferences=FoodPreferences(
            craving_profiles=["warm_comfort", "nostalgic", "fizzy_sweet_kick"],
            effort_to_eat="zero_mess",
        ),
        hard_constraints=HardConstraints(dietary_type="veg", max_budget_inr=300, max_eta_mins=30),
    )
    durations_ms: list[float] = []
    for _ in range(100):
        t0 = time.perf_counter()
        recs = engine.recommend(ctx, Location(), limit=4)
        durations_ms.append((time.perf_counter() - t0) * 1000.0)
        assert len(recs) >= 3

    durations_ms.sort()
    p99 = durations_ms[98]
    assert p99 < 120.0, f"P99 engine time {p99:.2f}ms exceeded 120ms budget"
