"""Swiggy Food MCP Client over Streamable HTTP (JSON-RPC 2.0 + SSE parsing)."""

from __future__ import annotations

import json
import uuid
from typing import Any

import httpx


class SwiggyMCPError(Exception):
    """Raised when Swiggy Food MCP call fails, times out, or returns an invalid payload."""


def parse_mcp_http_response(response: httpx.Response) -> dict[str, Any]:
    """Parse either direct application/json or Streamable HTTP text/event-stream payloads."""
    content_type = response.headers.get("content-type", "").lower()
    if "text/event-stream" not in content_type:
        return response.json()

    last_json: dict[str, Any] = {}
    for line in response.text.splitlines():
        stripped = line.strip()
        if stripped.startswith("data:"):
            raw_json = stripped[5:].strip()
            if not raw_json or raw_json == "[DONE]":
                continue
            try:
                parsed = json.loads(raw_json)
                if isinstance(parsed, dict):
                    last_json = parsed
            except json.JSONDecodeError:
                continue
    if not last_json:
        raise SwiggyMCPError("Empty SSE payload from Swiggy Food MCP")
    return last_json


def unwrap_mcp_tool_result(rpc_payload: dict[str, Any]) -> Any:
    """Extract normalized JSON/list data from standard MCP tools/call result structure."""
    if "error" in rpc_payload and rpc_payload["error"]:
        raise SwiggyMCPError(f"MCP error: {rpc_payload['error']}")

    result = rpc_payload.get("result", rpc_payload)
    if isinstance(result, dict):
        if "structuredContent" in result and result["structuredContent"] is not None:
            return result["structuredContent"]
        content = result.get("content")
        if isinstance(content, list):
            collected: list[Any] = []
            for block in content:
                if isinstance(block, dict) and block.get("type") == "text":
                    txt = str(block.get("text", "")).strip()
                    if not txt:
                        continue
                    try:
                        parsed = json.loads(txt)
                        if isinstance(parsed, list):
                            collected.extend(parsed)
                        else:
                            collected.append(parsed)
                    except json.JSONDecodeError:
                        collected.append({"text": txt})
                else:
                    collected.append(block)
            if len(collected) == 1:
                return collected[0]
            return collected
    return result


class SwiggyFoodMCPClient:
    """Async Streamable HTTP client for Swiggy's official Food MCP Server (Spec 10)."""

    def __init__(
        self,
        access_token: str,
        mcp_url: str = "https://mcp.swiggy.com/food",
        timeout_secs: float = 3.0,
    ) -> None:
        self.access_token = access_token.strip()
        self.mcp_url = mcp_url
        self.timeout_secs = timeout_secs
        self.session_id: str | None = None

    def _headers(self) -> dict[str, str]:
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
        }
        if self.session_id:
            headers["Mcp-Session-Id"] = self.session_id
        return headers

    async def _rpc(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
        if not self.access_token:
            raise SwiggyMCPError("Missing Swiggy OAuth access token")

        payload = {
            "jsonrpc": "2.0",
            "id": f"moodbite_{uuid.uuid4().hex[:8]}",
            "method": method,
            "params": params,
        }
        last_exc: Exception | None = None
        timeout = httpx.Timeout(self.timeout_secs)

        # Spec 10 Rule 6: 3.0s budget with 1 graceful retry before fallback
        async with httpx.AsyncClient(timeout=timeout) as client:
            for _attempt in range(2):
                try:
                    resp = await client.post(self.mcp_url, json=payload, headers=self._headers())
                    if resp.headers.get("mcp-session-id"):
                        self.session_id = resp.headers["mcp-session-id"]
                    resp.raise_for_status()
                    return parse_mcp_http_response(resp)
                except Exception as exc:
                    last_exc = exc
                    continue

        raise SwiggyMCPError(f"Swiggy MCP call '{method}' failed: {last_exc}")

    async def initialize(self) -> dict[str, Any]:
        return await self._rpc(
            "initialize",
            {
                "protocolVersion": "2025-03-26",
                "capabilities": {},
                "clientInfo": {"name": "moodbite-ai", "version": "0.1.0"},
            },
        )

    async def call_tool(self, tool_name: str, arguments: dict[str, Any]) -> Any:
        rpc_resp = await self._rpc(
            "tools/call",
            {"name": tool_name, "arguments": arguments},
        )
        return unwrap_mcp_tool_result(rpc_resp)

    async def get_addresses(self) -> list[dict[str, Any]]:
        data = await self.call_tool("get_addresses", {})
        if isinstance(data, dict):
            return list(data.get("addresses") or data.get("data") or [])
        return list(data) if isinstance(data, list) else []

    async def search_restaurants(self, query: str, address_id: str) -> list[dict[str, Any]]:
        data = await self.call_tool("search_restaurants", {"query": query, "address_id": address_id})
        if isinstance(data, dict):
            return list(data.get("restaurants") or data.get("results") or data.get("data") or [])
        return list(data) if isinstance(data, list) else []

    async def search_craving_dishes(self, query: str, address_id: str) -> list[dict[str, Any]]:
        data = await self.call_tool("search_menu", {"query": query, "address_id": address_id})
        if isinstance(data, dict):
            return list(data.get("items") or data.get("dishes") or data.get("results") or data.get("restaurants") or [])
        return list(data) if isinstance(data, list) else []

    async def get_restaurant_menu(self, restaurant_id: str, address_id: str) -> dict[str, Any]:
        data = await self.call_tool(
            "get_restaurant_menu",
            {"restaurant_id": restaurant_id, "address_id": address_id},
        )
        return data if isinstance(data, dict) else {"items": data if isinstance(data, list) else []}

    async def add_combo_to_cart(
        self,
        restaurant_id: str,
        item_ids: list[str],
        address_id: str,
    ) -> dict[str, Any]:
        items_payload = [{"item_id": iid, "quantity": 1} for iid in item_ids]
        data = await self.call_tool(
            "update_food_cart",
            {
                "restaurant_id": restaurant_id,
                "items": items_payload,
                "address_id": address_id,
            },
        )
        return data if isinstance(data, dict) else {"status": "updated", "raw": data}

    async def fetch_food_coupons(self, restaurant_id: str, address_id: str) -> list[dict[str, Any]]:
        data = await self.call_tool(
            "fetch_food_coupons",
            {"restaurant_id": restaurant_id, "address_id": address_id},
        )
        if isinstance(data, dict):
            return list(data.get("coupons") or data.get("offers") or [])
        return list(data) if isinstance(data, list) else []
