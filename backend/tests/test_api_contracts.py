"""End-to-end API contract tests for REST, SSE streaming, refine, and cart."""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_health_and_catalog_stats(client: TestClient) -> None:
    h = client.get("/health")
    assert h.status_code == 200
    h_body = h.json()
    assert h_body["status"] == "ok"
    assert h_body["llm_provider"] == "offline"
    assert h_body["catalog_items"] >= 150
    assert "X-Process-Time-Ms" in h.headers

    s = client.get("/api/v1/catalog/stats")
    assert s.status_code == 200
    assert s.json()["total_items"] >= 150


def test_full_chat_refine_session_and_cart_flow(client: TestClient) -> None:
    sess_id = "test_e2e_flow_01"

    # Turn 1: high-signal message -> immediate recommendations
    r1 = client.post(
        "/api/v1/chat/turn",
        json={
            "session_id": sess_id,
            "user_id": "usr_4412",
            "message": "super tired and mood is kinda off, want something fast that cheers me up",
            "location": {"lat": 28.6139, "lng": 77.2090},
            "active_filters": {"dietary_type": "veg"},
        },
    )
    assert r1.status_code == 200
    d1 = r1.json()
    assert d1["action"] == "recommend_combos"
    assert d1["turn_count"] == 1
    assert len(d1["recommendations"]) >= 3
    first_combo = d1["recommendations"][0]

    # Refine: Under ₹250
    ref = client.post(
        "/api/v1/chat/refine",
        json={
            "session_id": sess_id,
            "user_id": "usr_4412",
            "chip": "Under ₹250",
            "location": {"lat": 28.6139, "lng": 77.2090},
        },
    )
    assert ref.status_code == 200
    ref_body = ref.json()
    assert ref_body["action"] == "recommend_combos"
    assert len(ref_body["recommendations"]) >= 3
    assert all(c["total_price_inr"] <= 250 for c in ref_body["recommendations"])

    # Add combo to cart
    target = ref_body["recommendations"][0]
    add = client.post(
        "/api/v1/cart/add",
        json={"session_id": sess_id, "combo_id": target["combo_id"], "quantity": 1},
    )
    assert add.status_code == 200
    cart_body = add.json()
    assert cart_body["total_items"] == 1
    assert cart_body["total_price_inr"] == target["total_price_inr"]

    # Fetch session detail
    sess = client.get(f"/api/v1/sessions/{sess_id}")
    assert sess.status_code == 200
    assert sess.json()["cart"]["total_items"] == 1
    assert sess.json()["user_context"]["hard_constraints"]["dietary_type"] == "veg"

    # Remove combo from cart
    rem = client.delete(f"/api/v1/cart/{sess_id}/{target['combo_id']}")
    assert rem.status_code == 200
    assert rem.json()["total_items"] == 0

    # Ensure non-existing combo returns 404
    bad_add = client.post(
        "/api/v1/cart/add",
        json={"session_id": sess_id, "combo_id": "cmb_fake_999", "quantity": 1},
    )
    assert bad_add.status_code == 404
    assert first_combo["combo_id"] != "cmb_fake_999"


def test_sse_stream_endpoint(client: TestClient) -> None:
    with client.stream(
        "POST",
        "/api/v1/chat/turn/stream",
        json={
            "session_id": "test_sse_01",
            "user_id": "usr_sse",
            "message": "had an awful meeting, need spicy comfort food right now",
            "location": {"lat": 28.6139, "lng": 77.2090},
        },
    ) as resp:
        assert resp.status_code == 200
        raw_text = "".join(resp.iter_text())
        assert "event: status" in raw_text
        assert "event: token" in raw_text
        assert "event: recommendations" in raw_text
        assert "event: done" in raw_text


def test_daily_request_limit_20_per_day(client: TestClient) -> None:
    """Enforces 20 chat requests per day and returns 429 on the 21st request."""
    h0 = client.get("/health").json()
    assert h0["daily_request_limit"] == 20
    assert h0["daily_requests_used"] == 0
    assert h0["daily_requests_remaining"] == 20

    for i in range(1, 21):
        resp = client.post(
            "/api/v1/chat/turn",
            json={
                "session_id": f"quota_sess_{i}",
                "user_id": "usr_quota",
                "message": "hi",
            },
        )
        assert resp.status_code == 200
        assert resp.headers["X-RateLimit-Limit"] == "20"
        assert resp.headers["X-RateLimit-Remaining"] == str(20 - i)

    blocked = client.post(
        "/api/v1/chat/turn",
        json={
            "session_id": "quota_sess_21",
            "user_id": "usr_quota",
            "message": "hi again",
        },
    )
    assert blocked.status_code == 429
    detail = blocked.json()["detail"]
    assert detail["code"] == "DAILY_LIMIT_REACHED"
    assert detail["limit"] == 20
    assert detail["remaining"] == 0

    h_after = client.get("/health").json()
    assert h_after["daily_requests_used"] == 20
    assert h_after["daily_requests_remaining"] == 0


def test_stress_report_endpoint(client: TestClient) -> None:
    """Exposes the verified 30-prompt stress suite JSON scorecard."""
    resp = client.get("/api/v1/stress-report")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total_prompts"] == 30
    assert body["passed"] == 30
    assert body["failed"] == 0
    assert body["safety_failures"] == 0
    assert body["all_1_to_6_and_10_safe"] is True
    assert len(body["results"]) == 30


