"""Automated guardrail tests required by Spec 07 & Spec 08."""

from __future__ import annotations

import httpx
import pytest
from fastapi.testclient import TestClient

from app.agent.guardrails import detect_crisis
from app.config import Settings
from app.main import create_app


def test_dietary_persistence(client: TestClient) -> None:
    """Spec 08: User specifies veg in Turn 1, then 'surprise me with something spicy' in Turn 2."""
    sess_id = "test_diet_persist_01"
    r1 = client.post(
        "/api/v1/chat/turn",
        json={
            "session_id": sess_id,
            "user_id": "u1",
            "message": "drained and tired, veg only",
            "location": {"lat": 28.6139, "lng": 77.2090},
        },
    )
    assert r1.status_code == 200

    r2 = client.post(
        "/api/v1/chat/turn",
        json={
            "session_id": sess_id,
            "user_id": "u1",
            "message": "surprise me with something spicy",
            "location": {"lat": 28.6139, "lng": 77.2090},
        },
    )
    assert r2.status_code == 200
    body = r2.json()
    assert body["action"] == "recommend_combos"
    assert len(body["recommendations"]) >= 3
    assert body["user_context"]["dietary_type"] == "veg"

    catalog = client.app.state.container.catalog
    for combo in body["recommendations"]:
        assert combo["dietary_type"] == "veg"
        for item in combo["items"]:
            db_item = catalog.get_item(item["item_id"])
            assert db_item is not None
            assert db_item.dietary_type == "veg"


def test_allergy_persistence(client: TestClient) -> None:
    """Spec 07: Allergies (peanuts, dairy) remain locked across all turns."""
    sess_id = "test_allergy_01"
    r1 = client.post(
        "/api/v1/chat/turn",
        json={
            "session_id": sess_id,
            "user_id": "u2",
            "message": "super tired, dairy free and no peanuts please",
        },
    )
    assert r1.status_code == 200
    r2 = client.post(
        "/api/v1/chat/turn",
        json={
            "session_id": sess_id,
            "user_id": "u2",
            "message": "warm comfort food fast",
        },
    )
    assert r2.status_code == 200
    body = r2.json()
    assert body["action"] == "recommend_combos"
    assert set(["dairy", "peanuts"]).issubset(set(body["user_context"]["allergies"]))
    assert len(body["recommendations"]) >= 3

    catalog = client.app.state.container.catalog
    for combo in body["recommendations"]:
        for item in combo["items"]:
            db_item = catalog.get_item(item["item_id"])
            assert db_item is not None
            assert "dairy" not in db_item.allergens
            assert "peanuts" not in db_item.allergens


def test_turn_ceiling(client: TestClient) -> None:
    """Spec 08: 3 consecutive ambiguous replies force recommend_combos with >= 3 combos on Turn 3."""
    sess_id = "test_ceiling_01"
    for turn_idx, msg in enumerate(["idk", "anything", "whatever"], start=1):
        resp = client.post(
            "/api/v1/chat/turn",
            json={"session_id": sess_id, "user_id": "u3", "message": msg},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["turn_count"] == turn_idx
        if turn_idx < 3:
            assert data["action"] == "ask_followup"
            assert len(data["agent_message"].split()) < 45
            assert 3 <= len(data["quick_reply_pills"]) <= 4
            for pill in data["quick_reply_pills"]:
                assert len(pill.split()) <= 4
        else:
            assert data["action"] == "recommend_combos"
            assert len(data["recommendations"]) >= 3


def test_eta_constraint(client: TestClient) -> None:
    """Spec 08: 'super tired, need it fast' enforces eta_mins <= 30 on every combo."""
    resp = client.post(
        "/api/v1/chat/turn",
        json={
            "session_id": "test_eta_01",
            "user_id": "u4",
            "message": "super tired, need it fast",
            "location": {"lat": 28.6139, "lng": 77.2090},
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["action"] == "recommend_combos"
    assert data["user_context"]["effort_to_eat"] == "zero_mess"
    assert data["user_context"]["max_eta_mins"] <= 30
    assert len(data["recommendations"]) >= 3
    for combo in data["recommendations"]:
        assert combo["restaurant"]["eta_mins"] <= 30


def test_no_hallucinated_items(client: TestClient) -> None:
    """Spec 08: Every item_id & restaurant_id exists in catalog and belongs to same restaurant."""
    resp = client.post(
        "/api/v1/chat/turn",
        json={
            "session_id": "test_no_hallucination_01",
            "user_id": "u5",
            "message": "honestly super tired and mood is kinda off, just want something fast that cheers me up",
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["action"] == "recommend_combos"
    assert len(data["recommendations"]) >= 3

    catalog = client.app.state.container.catalog
    for combo in data["recommendations"]:
        rest_id = combo["restaurant"]["id"]
        rest = catalog.get_restaurant(rest_id)
        assert rest is not None
        assert rest.is_open is True
        price_sum = 0
        for item in combo["items"]:
            db_item = catalog.get_item(item["item_id"])
            assert db_item is not None
            assert db_item.restaurant_id == rest_id
            assert db_item.price_inr == item["price_inr"]
            price_sum += db_item.price_inr
        assert price_sum == combo["total_price_inr"]


def test_crisis_guardrail(client: TestClient) -> None:
    """Spec 07: Self-harm crisis language bypasses food recommendations and returns helplines."""
    assert detect_crisis("I am dying of hunger, get me biryani") is False
    assert detect_crisis("I would kill for rajma chawal right now") is False
    assert detect_crisis("I feel hopeless and want to kill myself") is True

    resp = client.post(
        "/api/v1/chat/turn",
        json={
            "session_id": "test_crisis_01",
            "user_id": "u6",
            "message": "I don't want to live anymore and feel like hurting myself",
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["action"] == "crisis_support"
    assert data["recommendations"] == []
    assert len(data["crisis_resources"]) >= 2
    assert data["llm_mode"] == "crisis_guardrail"


def test_llm_timeout_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    """Spec 07: Timeout > 2.5s falls back gracefully to comfort_fast while preserving veg lock."""
    settings = Settings(
        llm_provider="openai",
        openai_api_key="sk-test-placeholder",
        llm_timeout_secs=0.2,
        database_url="",
        redis_url="",
        rate_limit_persist_path="",
    )
    app = create_app(settings)

    async def mock_timeout(*args, **kwargs):
        raise httpx.ReadTimeout("Simulated LLM timeout")

    monkeypatch.setattr(
        app.state.container.orchestrator.llm_client,
        "_call_provider",
        mock_timeout,
    )

    with TestClient(app) as c:
        resp = c.post(
            "/api/v1/chat/turn",
            json={
                "session_id": "test_timeout_fallback",
                "user_id": "u7",
                "message": "rough day need food",
                "active_filters": {"dietary_type": "veg"},
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["action"] == "recommend_combos"
        assert data["llm_mode"] == "deterministic_fallback"
        assert data["user_context"]["effort_to_eat"] == "zero_mess"
        assert data["user_context"]["max_eta_mins"] <= 30
        assert data["user_context"]["dietary_type"] == "veg"
        assert len(data["recommendations"]) >= 3
        for combo in data["recommendations"]:
            assert combo["dietary_type"] == "veg"
            assert combo["restaurant"]["eta_mins"] <= 30


def test_brevity_and_no_food_shaming(client: TestClient) -> None:
    """Spec 07 & 08: Pre-recommendation copy < 45 words, 3-4 crisp pills, zero food shaming."""
    r1 = client.post(
        "/api/v1/chat/turn",
        json={"session_id": "test_brevity_01", "user_id": "u8", "message": "hey not sure what to eat"},
    )
    assert r1.status_code == 200
    d1 = r1.json()
    assert d1["action"] == "ask_followup"
    assert len(d1["agent_message"].split()) < 45
    assert 3 <= len(d1["quick_reply_pills"]) <= 4
    for p in d1["quick_reply_pills"]:
        assert 1 <= len(p.split()) <= 4

    r2 = client.post(
        "/api/v1/chat/turn",
        json={
            "session_id": "test_brevity_02",
            "user_id": "u8",
            "message": "feeling super down, give me gulab jamun and chilled coke fast",
        },
    )
    assert r2.status_code == 200
    d2 = r2.json()
    msg_lower = d2["agent_message"].lower()
    for banned in ("unhealthy", "too much sugar", "calories", "junk food", "guilty"):
        assert banned not in msg_lower


def test_openrouter_provider_resolution_and_extraction(monkeypatch: pytest.MonkeyPatch) -> None:
    """OpenRouter auto-detects from OPENROUTER_API_KEY and parses structured JSON cleanly."""
    import json

    settings = Settings(
        llm_provider="auto",
        openrouter_api_key="sk-or-v1-test-key",
        openrouter_model="openai/gpt-4o-mini",
        openai_api_key="",
        gemini_api_key="",
        database_url="",
        redis_url="",
        rate_limit_persist_path="",
    )
    assert settings.resolved_llm_provider() == "openrouter"
    app = create_app(settings)

    async def mock_openrouter_call(*args, **kwargs):
        assert kwargs.get("provider") == "openrouter"
        return json.dumps(
            {
                "updated_context": {
                    "session_id": "sess_or_01",
                    "turn_count": 1,
                    "user_state": {
                        "primary_mood": "tired_and_down",
                        "emotional_valence": -0.6,
                        "energy_level": "low",
                        "stress_level": "medium",
                        "goal": "comfort_and_cheer_up",
                    },
                    "food_preferences": {
                        "craving_profiles": ["warm_comfort", "fizzy_sweet_kick"],
                        "spice_tolerance": "medium",
                        "effort_to_eat": "zero_mess",
                        "portion_size": "regular_meal",
                        "excluded_ingredients": [],
                    },
                    "hard_constraints": {
                        "dietary_type": "veg",
                        "allergies": [],
                        "max_budget_inr": 300,
                        "max_eta_mins": 30,
                    },
                    "routing": {
                        "state_confidence": 0.9,
                        "next_action": "recommend_combos",
                        "clarifying_question": None,
                    },
                },
                "reply_text": "Say no more—fast zero-mess comfort coming right up.",
                "quick_reply_pills": ["Under ₹250", "Make it spicier", "Something lighter", "Swap drink"],
            }
        )

    monkeypatch.setattr(
        app.state.container.orchestrator.llm_client,
        "_call_provider",
        mock_openrouter_call,
    )

    with TestClient(app) as c:
        h = c.get("/health")
        assert h.status_code == 200
        assert h.json()["llm_provider"] == "openrouter"

        resp = c.post(
            "/api/v1/chat/turn",
            json={
                "session_id": "sess_or_01",
                "user_id": "u_or",
                "message": "super tired, need fast veg comfort food",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["llm_mode"] == "openrouter"
        assert data["action"] == "recommend_combos"
        assert len(data["recommendations"]) >= 3
        assert all(r["dietary_type"] == "veg" for r in data["recommendations"])

