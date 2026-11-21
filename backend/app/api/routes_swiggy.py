"""Swiggy Food MCP OAuth 2.1 + PKCE and address endpoints (Spec 10)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import RedirectResponse

from app.api.deps import AppContainer, get_container
from app.mcp.swiggy_client import SwiggyFoodMCPClient, SwiggyMCPError
from app.schemas.api import (
    SwiggyAddress,
    SwiggyAuthStatusResponse,
    SwiggyTokenConnectRequest,
)

router = APIRouter(tags=["swiggy-mcp"])


@router.get("/auth/swiggy/login")
async def swiggy_oauth_login(
    container: AppContainer = Depends(get_container),
) -> RedirectResponse:
    url = await container.swiggy_oauth.build_authorization_url(container.swiggy_tokens)
    return RedirectResponse(url=url, status_code=status.HTTP_302_FOUND)


@router.get("/auth/swiggy/callback")
async def swiggy_oauth_callback(
    code: str = Query(...),
    state: str = Query(...),
    container: AppContainer = Depends(get_container),
) -> RedirectResponse:
    pending = container.swiggy_tokens.pop_pending_state(state)
    if pending is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "INVALID_OAUTH_STATE", "message": "OAuth state expired or invalid."},
        )
    try:
        token_data = await container.swiggy_oauth.exchange_code(code=code, pending=pending)
        access_token = str(token_data.get("access_token") or "")
        refresh_token = str(token_data.get("refresh_token") or "")
        if not access_token:
            raise ValueError("Missing access_token in OAuth response")
        container.swiggy_tokens.save_token(access_token=access_token, refresh_token=refresh_token)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={"code": "SWIGGY_OAUTH_EXCHANGE_FAILED", "message": str(exc)},
        ) from exc

    return RedirectResponse(
        url=f"{container.settings.swiggy_frontend_redirect_uri}?swiggy=connected",
        status_code=status.HTTP_302_FOUND,
    )


@router.post("/auth/swiggy/token", response_model=SwiggyAuthStatusResponse)
async def connect_swiggy_token(
    payload: SwiggyTokenConnectRequest,
    container: AppContainer = Depends(get_container),
) -> SwiggyAuthStatusResponse:
    container.swiggy_tokens.save_token(
        access_token=payload.access_token,
        address_id=payload.address_id,
    )
    return await get_swiggy_status(container=container)


@router.post("/auth/swiggy/logout", response_model=SwiggyAuthStatusResponse)
async def logout_swiggy(
    container: AppContainer = Depends(get_container),
) -> SwiggyAuthStatusResponse:
    container.swiggy_tokens.clear()
    return SwiggyAuthStatusResponse(
        connected=False,
        mcp_url=container.settings.swiggy_mcp_url,
        demo_fallback_mode=container.settings.demo_fallback_mode,
        selected_address_id=None,
        addresses=[],
    )


@router.get("/auth/swiggy/status", response_model=SwiggyAuthStatusResponse)
async def get_swiggy_status(
    container: AppContainer = Depends(get_container),
) -> SwiggyAuthStatusResponse:
    addresses: list[SwiggyAddress] = []
    if container.swiggy_tokens.is_connected and not container.settings.demo_fallback_mode:
        try:
            client = SwiggyFoodMCPClient(
                access_token=container.swiggy_tokens.access_token,
                mcp_url=container.settings.swiggy_mcp_url,
                timeout_secs=container.settings.swiggy_mcp_timeout_secs,
            )
            raw_addrs = await client.get_addresses()
            for idx, addr in enumerate(raw_addrs):
                aid = str(addr.get("address_id") or addr.get("id") or f"addr_{idx}")
                addresses.append(
                    SwiggyAddress(
                        address_id=aid,
                        label=str(addr.get("label") or addr.get("tag") or "Saved Address"),
                        address_line=str(addr.get("address_line") or addr.get("formatted_address") or addr.get("address") or ""),
                        lat=addr.get("lat"),
                        lng=addr.get("lng"),
                    )
                )
            if addresses and not container.swiggy_tokens.selected_address_id:
                container.swiggy_tokens.selected_address_id = addresses[0].address_id
        except Exception:
            pass

    return SwiggyAuthStatusResponse(
        connected=container.swiggy_tokens.is_connected,
        mcp_url=container.settings.swiggy_mcp_url,
        demo_fallback_mode=container.settings.demo_fallback_mode,
        selected_address_id=container.swiggy_tokens.selected_address_id or None,
        addresses=addresses,
    )


@router.get("/api/v1/swiggy/addresses", response_model=list[SwiggyAddress])
async def list_swiggy_addresses(
    container: AppContainer = Depends(get_container),
) -> list[SwiggyAddress]:
    status_resp = await get_swiggy_status(container=container)
    return status_resp.addresses
