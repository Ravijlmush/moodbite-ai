"""OAuth 2.1 + PKCE (S256) authentication and token store for Swiggy Food MCP."""

from __future__ import annotations

import base64
import hashlib
import secrets
import time
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlencode, urlparse

import httpx


def generate_pkce_pair() -> tuple[str, str]:
    """Generate RFC 7636 PKCE code_verifier and S256 code_challenge."""
    verifier = base64.urlsafe_b64encode(secrets.token_bytes(32)).rstrip(b"=").decode("ascii")
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")
    return verifier, challenge


@dataclass
class PendingOAuthState:
    state: str
    code_verifier: str
    token_endpoint: str
    client_id: str
    redirect_uri: str
    created_at: float = field(default_factory=time.time)


@dataclass
class SwiggyTokenStore:
    """Ephemeral OAuth 2.1 token & address preference store for Swiggy Food MCP."""

    access_token: str = ""
    refresh_token: str = ""
    selected_address_id: str = ""
    client_id: str = ""
    pending_states: dict[str, PendingOAuthState] = field(default_factory=dict)

    @property
    def is_connected(self) -> bool:
        return bool(self.access_token.strip())

    def save_token(self, access_token: str, refresh_token: str = "", address_id: str | None = None) -> None:
        self.access_token = access_token.strip()
        if refresh_token:
            self.refresh_token = refresh_token.strip()
        if address_id:
            self.selected_address_id = address_id.strip()

    def clear(self) -> None:
        self.access_token = ""
        self.refresh_token = ""
        self.selected_address_id = ""

    def create_pending_state(
        self,
        *,
        code_verifier: str,
        token_endpoint: str,
        client_id: str,
        redirect_uri: str,
    ) -> str:
        now = time.time()
        expired = [k for k, v in self.pending_states.items() if now - v.created_at > 600]
        for k in expired:
            del self.pending_states[k]
        state = secrets.token_urlsafe(24)
        self.pending_states[state] = PendingOAuthState(
            state=state,
            code_verifier=code_verifier,
            token_endpoint=token_endpoint,
            client_id=client_id,
            redirect_uri=redirect_uri,
        )
        return state

    def pop_pending_state(self, state: str) -> PendingOAuthState | None:
        return self.pending_states.pop(state, None)


class SwiggyOAuthClient:
    """Discovers MCP OAuth 2.1 metadata, registers localhost client if needed, and exchanges PKCE codes."""

    def __init__(self, mcp_url: str, redirect_uri: str, configured_client_id: str = "") -> None:
        self.mcp_url = mcp_url.rstrip("/")
        self.redirect_uri = redirect_uri
        self.configured_client_id = configured_client_id.strip()
        parsed = urlparse(self.mcp_url)
        self.origin = f"{parsed.scheme}://{parsed.netloc}"

    async def discover_metadata(self) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=4.0) as client:
            auth_server = self.origin
            try:
                prm = await client.get(f"{self.origin}/.well-known/oauth-protected-resource")
                if prm.status_code == 200:
                    data = prm.json()
                    servers = data.get("authorization_servers") or []
                    if servers:
                        auth_server = str(servers[0]).rstrip("/")
            except Exception:
                pass

            try:
                asm = await client.get(f"{auth_server}/.well-known/oauth-authorization-server")
                if asm.status_code == 200:
                    return asm.json()
            except Exception:
                pass

        return {
            "authorization_endpoint": f"{self.origin}/oauth/authorize",
            "token_endpoint": f"{self.origin}/oauth/token",
            "registration_endpoint": f"{self.origin}/oauth/register",
        }

    async def ensure_client_id(self, metadata: dict[str, Any], token_store: SwiggyTokenStore) -> str:
        if self.configured_client_id:
            return self.configured_client_id
        if token_store.client_id:
            return token_store.client_id

        reg_endpoint = metadata.get("registration_endpoint")
        if reg_endpoint:
            try:
                async with httpx.AsyncClient(timeout=4.0) as client:
                    resp = await client.post(
                        str(reg_endpoint),
                        json={
                            "client_name": "MoodBite AI Localhost Prototype",
                            "redirect_uris": [self.redirect_uri],
                            "grant_types": ["authorization_code", "refresh_token"],
                            "response_types": ["code"],
                            "token_endpoint_auth_method": "none",
                        },
                    )
                    if resp.status_code in (200, 201):
                        cid = resp.json().get("client_id")
                        if cid:
                            token_store.client_id = str(cid)
                            return token_store.client_id
            except Exception:
                pass

        return "moodbite-localhost-client"

    async def build_authorization_url(self, token_store: SwiggyTokenStore) -> str:
        metadata = await self.discover_metadata()
        client_id = await self.ensure_client_id(metadata, token_store)
        verifier, challenge = generate_pkce_pair()
        auth_endpoint = str(metadata.get("authorization_endpoint") or f"{self.origin}/oauth/authorize")
        token_endpoint = str(metadata.get("token_endpoint") or f"{self.origin}/oauth/token")

        state = token_store.create_pending_state(
            code_verifier=verifier,
            token_endpoint=token_endpoint,
            client_id=client_id,
            redirect_uri=self.redirect_uri,
        )
        query = urlencode(
            {
                "response_type": "code",
                "client_id": client_id,
                "redirect_uri": self.redirect_uri,
                "code_challenge": challenge,
                "code_challenge_method": "S256",
                "state": state,
                "scope": "food:read food:cart",
            }
        )
        return f"{auth_endpoint}?{query}"

    async def exchange_code(
        self,
        *,
        code: str,
        pending: PendingOAuthState,
    ) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.post(
                pending.token_endpoint,
                data={
                    "grant_type": "authorization_code",
                    "code": code,
                    "redirect_uri": pending.redirect_uri,
                    "client_id": pending.client_id,
                    "code_verifier": pending.code_verifier,
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            resp.raise_for_status()
            return resp.json()
