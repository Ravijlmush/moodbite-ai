"""Unit & integration tests for Spec 10 Swiggy Food MCP integration."""

from __future__ import annotations

import base64
import hashlib
import json

import httpx
import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from app.mcp.swiggy_client import SwiggyFoodMCPClient, parse_mcp_http_response, unwrap_mcp_tool_result
from app.mcp.swiggy_oauth import SwiggyTokenStore, generate_pkce_pair


def test_pkce_s256_and_token_store() -> None:
    verifier, challenge = generate_pkce_pair()
    assert len(verifier) >= 43
    expected = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode("ascii")).digest()).rstrip(b"=").decode("ascii")
    assert challenge == expected

    store = SwiggyTokenStore()
    assert store.is_connected is False
    store.save_token("tok_swiggy_123", address_id="addr_9921")
    assert store.is_connected is True
    assert store.selected_address_id == "addr_9921"
    store.clear()
    assert store.is_connected is False


def test_mcp_sse_response_parser() -> None:
    sse_body = (
        "event: message\n"
        'data: {"jsonrpc":"2.0","id":"1","result":{"content":[{"type":"text","text":"{\\"addresses\\":[{\\"address_id\\":\\"addr_9921\\",\\"label\\":\\"Home\\"}]}"}]}}\n\n'
    )
    resp = httpx.Response(
        200,
        headers={"content-type": "text/event-stream"},
        text=sse_body,
    )
    rpc = parse_mcp_http_response(resp)
    unwrapped = unwrap_mcp_tool_result(rpc)
    assert unwrapped["addresses"][0]["address_id"] == "addr_9921"


def test_swiggy_mcp_live_search_rank_and_add_combo(monkeypatch: pytest.MonkeyPatch) -> None:
    """Tests live Swiggy MCP search -> mood ranking -> /api/v1/cart/add-combo."""
    settings = Settings(
        llm_provider="offline",
        demo_fallback_mode=False,
        database_url="",
        redis_url="",
        daily_request_limit=50,
        rate_limit_persist_path="",
    )
    app = create_app(settings)

    async def fake_call_tool(self, tool_name: str, arguments: dict):
        if tool_name == "get_addresses":
            return {"addresses": [{"address_id": "addr_9921", "label": "Home", "address_line": "Indiranagar, Bengaluru"}]}
        if tool_name == "search_menu":
            return [
                {
                    "restaurant_id": "rest_live_1",
                    "restaurant_name": "Punjabi Angithi Live",
                    "restaurant_rating": 4.5,
                    "sla_mins": 21,
                    "items": [
                        {"item_id": "sw_101", "name": "Homestyle Rajma Chawal Bowl", "price_inr": 179, "is_veg": True},
                        {"item_id": "sw_102", "name": "Coca-Cola Can (300ml)", "price_inr": 40, "is_veg": True},
                    ],
                },
                {
                    "restaurant_id": "rest_live_2",
                    "restaurant_name": "Khichdi Express Live",
                    "restaurant_rating": 4.6,
                    "sla_mins": 18,
                    "items": [
                        {"item_id": "sw_201", "name": "Ghee Dal Khichdi Bowl", "price_inr": 149, "is_veg": True},
                        {"item_id": "sw_202", "name": "Chilled Limca (300ml)", "price_inr": 40, "is_veg": True},
                    ],
                },
                {
                    "restaurant_id": "rest_live_3",
                    "restaurant_name": "Kathi Roll Live",
                    "restaurant_rating": 4.4,
                    "sla_mins": 24,
                    "items": [
                        {"item_id": "sw_301", "name": "Paneer Tikka Roll", "price_inr": 175, "is_veg": True},
                        {"item_id": "sw_302", "name": "Masala Chaas", "price_inr": 45, "is_veg": True},
                        {"item_id": "sw_303", "name": "Chicken Tikka Roll", "price_inr": 199, "is_veg": False},
                    ],
                },
            ]
        if tool_name == "fetch_food_coupons":
            return [{"coupon_code": "SWIGGYIT ₹50 OFF"}]
        if tool_name == "update_food_cart":
            return {"status": "cart_updated", "items": arguments["items"]}
        return {}

    monkeypatch.setattr(SwiggyFoodMCPClient, "call_tool", fake_call_tool)

    with TestClient(app) as c:
        tok_resp = c.post("/auth/swiggy/token", json={"access_token": "live_swiggy_tok_001"})
        assert tok_resp.status_code == 200
        assert tok_resp.json()["connected"] is True
        assert tok_resp.json()["selected_address_id"] == "addr_9921"

        chat_resp = c.post(
            "/api/v1/chat/turn",
            json={
                "session_id": "sess_swiggy_live",
                "message": "super tired and mood is kinda off, want something fast that cheers me up",
                "active_filters": {"dietary_type": "veg"},
            },
        )
        assert chat_resp.status_code == 200
        body = chat_resp.json()
        assert body["catalog_source"] == "swiggy_mcp_live"
        assert len(body["recommendations"]) == 3
        assert body["recommendations"][0]["source"] == "swiggy_mcp_live"
        assert body["recommendations"][0]["coupon_badge"] == "SWIGGYIT ₹50 OFF"
        # Ensure Chicken Tikka Roll was filtered out by veg lock
        for rec in body["recommendations"]:
            assert rec["dietary_type"] == "veg"
            for it in rec["items"]:
                assert "chicken" not in it["name"].lower()

        chosen = body["recommendations"][0]
        cart_resp = c.post(
            "/api/v1/cart/add-combo",
            json={
                "session_id": "sess_swiggy_live",
                "restaurant_id": chosen["restaurant"]["id"],
                "item_ids": [it["item_id"] for it in chosen["items"]],
                "combo_id": chosen["combo_id"],
                "combo": chosen,
                "address_id": "addr_9921",
            },
        )
        assert cart_resp.status_code == 200
        cart_data = cart_resp.json()
        assert cart_data["swiggy_synced"] is True
        assert cart_data["total_items"] == 1


def test_swiggy_mcp_timeout_falls_back_gracefully(monkeypatch: pytest.MonkeyPatch) -> None:
    """Spec 10 Rule 6: If Swiggy MCP fails/times out (>3s), fall back to verified local catalog."""
    settings = Settings(
        llm_provider="offline",
        demo_fallback_mode=False,
        database_url="",
        redis_url="",
        daily_request_limit=50,
        rate_limit_persist_path="",
    )
    app = create_app(settings)

    async def fail_mcp(*args, **kwargs):
        raise httpx.ReadTimeout("Swiggy MCP timed out")

    monkeypatch.setattr(SwiggyFoodMCPClient, "call_tool", fail_mcp)

    with TestClient(app) as c:
        c.post("/auth/swiggy/token", json={"access_token": "tok_timeout"})
        resp = c.post(
            "/api/v1/chat/turn",
            json={
                "session_id": "sess_mcp_timeout",
                "message": "super tired and mood is off, veg only fast comfort",
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["catalog_source"] == "demo_fallback"
        assert len(body["recommendations"]) >= 3
        assert all(r["dietary_type"] == "veg" for r in body["recommendations"])
