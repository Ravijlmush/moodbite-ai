"""Cart management endpoints for + ADD COMBO TO CART and /api/v1/cart/add-combo (Swiggy MCP)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import AppContainer, get_container
from app.mcp.swiggy_client import SwiggyFoodMCPClient, SwiggyMCPError
from app.schemas.api import (
    AddComboToSwiggyCartRequest,
    AddToCartRequest,
    CartEntry,
    CartResponse,
)
from app.schemas.catalog import ComboItem, ComboRecommendation, ComboRestaurant

router = APIRouter(prefix="/api/v1/cart", tags=["cart"])


def _build_cart_response(
    session_id: str,
    entries: list[CartEntry],
    *,
    swiggy_synced: bool = False,
    swiggy_message: str | None = None,
) -> CartResponse:
    return CartResponse(
        session_id=session_id,
        items=entries,
        total_items=sum(e.quantity for e in entries),
        total_price_inr=sum(e.line_total_inr for e in entries),
        swiggy_synced=swiggy_synced,
        swiggy_message=swiggy_message,
    )


@router.post("/add", response_model=CartResponse)
async def add_combo_to_cart(
    payload: AddToCartRequest,
    container: AppContainer = Depends(get_container),
) -> CartResponse:
    session = await container.session_store.get_or_create(payload.session_id)

    target_combo = next(
        (rec for rec in session.last_recommendations if rec.combo_id == payload.combo_id),
        None,
    )
    if target_combo is None and payload.combo is not None and payload.combo.combo_id == payload.combo_id:
        if payload.combo.source == "swiggy_mcp_live":
            target_combo = payload.combo
        else:
            rest = container.catalog.get_restaurant(payload.combo.restaurant.id)
            if rest is not None and rest.is_open:
                all_valid = all(
                    (item := container.catalog.get_item(ci.item_id)) is not None
                    and item.restaurant_id == rest.id
                    and item.is_available
                    for ci in payload.combo.items
                )
                if all_valid:
                    target_combo = payload.combo

    if target_combo is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "COMBO_NOT_FOUND", "message": f"Combo '{payload.combo_id}' is not in session or catalog."},
        )

    existing = next((e for e in session.cart if e.combo.combo_id == payload.combo_id), None)
    if existing is not None:
        existing.quantity += payload.quantity
        existing.line_total_inr = existing.quantity * existing.combo.total_price_inr
    else:
        session.cart.append(
            CartEntry(
                combo=target_combo,
                quantity=payload.quantity,
                line_total_inr=payload.quantity * target_combo.total_price_inr,
            )
        )

    await container.session_store.save(session)
    return _build_cart_response(session.session_id, session.cart)


@router.post("/add-combo", response_model=CartResponse)
async def add_combo_to_swiggy_cart(
    payload: AddComboToSwiggyCartRequest,
    container: AppContainer = Depends(get_container),
) -> CartResponse:
    """Spec 10 Section 7.2: Calls SwiggyFoodMCPClient.add_combo_to_cart when connected, with local cart sync."""
    session = await container.session_store.get_or_create(payload.session_id)

    target_combo: ComboRecommendation | None = None
    if payload.combo_id:
        target_combo = next(
            (rec for rec in session.last_recommendations if rec.combo_id == payload.combo_id),
            None,
        )
    if target_combo is None and payload.combo is not None:
        target_combo = payload.combo
    if target_combo is None:
        # Construct validated combo from local catalog if items match
        rest = container.catalog.get_restaurant(payload.restaurant_id)
        if rest is not None and rest.is_open:
            found_items: list[ComboItem] = []
            for iid in payload.item_ids:
                db_it = container.catalog.get_item(iid)
                if db_it is not None and db_it.restaurant_id == rest.id and db_it.is_available:
                    found_items.append(
                        ComboItem(
                            item_id=db_it.id,
                            name=db_it.name,
                            price_inr=db_it.price_inr,
                            dietary_type=db_it.dietary_type,
                            category=db_it.category,
                        )
                    )
            if len(found_items) == len(payload.item_ids):
                total_p = sum(i.price_inr for i in found_items)
                target_combo = ComboRecommendation(
                    combo_id=payload.combo_id or f"cmb_{rest.id}_{'_'.join(payload.item_ids)}",
                    mood_badge="SWIGGY COMBO",
                    title=" + ".join(i.name for i in found_items),
                    restaurant=ComboRestaurant(
                        id=rest.id,
                        name=rest.name,
                        rating=rest.rating,
                        eta_mins=rest.base_prep_mins + 8,
                    ),
                    items=found_items,
                    total_price_inr=total_p,
                    why_it_fits="Added directly via MoodBite × Swiggy Food MCP.",
                    match_score=0.92,
                )

    if target_combo is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "COMBO_NOT_FOUND", "message": "Could not resolve combo items for cart."},
        )

    swiggy_synced = False
    swiggy_message = "Added to MoodBite session cart (connect Swiggy MCP to sync live)."
    active_token = (payload.swiggy_access_token or container.swiggy_tokens.access_token or "").strip()
    active_addr = (payload.address_id or container.swiggy_tokens.selected_address_id or "default").strip()

    if active_token and not container.settings.demo_fallback_mode:
        try:
            mcp_client = SwiggyFoodMCPClient(
                access_token=active_token,
                mcp_url=container.settings.swiggy_mcp_url,
                timeout_secs=container.settings.swiggy_mcp_timeout_secs,
            )
            await mcp_client.add_combo_to_cart(
                restaurant_id=payload.restaurant_id,
                item_ids=payload.item_ids,
                address_id=active_addr,
            )
            swiggy_synced = True
            swiggy_message = "Synced live via Swiggy Food MCP update_food_cart."
        except SwiggyMCPError as exc:
            swiggy_message = f"Saved locally; Swiggy MCP sync skipped ({exc})."

    existing = next((e for e in session.cart if e.combo.combo_id == target_combo.combo_id), None)
    if existing is not None:
        existing.quantity += 1
        existing.line_total_inr = existing.quantity * existing.combo.total_price_inr
    else:
        session.cart.append(
            CartEntry(
                combo=target_combo,
                quantity=1,
                line_total_inr=target_combo.total_price_inr,
            )
        )

    await container.session_store.save(session)
    return _build_cart_response(
        session.session_id,
        session.cart,
        swiggy_synced=swiggy_synced,
        swiggy_message=swiggy_message,
    )


@router.get("/{session_id}", response_model=CartResponse)
async def get_cart(
    session_id: str,
    container: AppContainer = Depends(get_container),
) -> CartResponse:
    session = await container.session_store.get_or_create(session_id)
    return _build_cart_response(session.session_id, session.cart)


@router.delete("/{session_id}/{combo_id}", response_model=CartResponse)
async def remove_from_cart(
    session_id: str,
    combo_id: str,
    container: AppContainer = Depends(get_container),
) -> CartResponse:
    session = await container.session_store.get_or_create(session_id)
    session.cart = [e for e in session.cart if e.combo.combo_id != combo_id]
    await container.session_store.save(session)
    return _build_cart_response(session.session_id, session.cart)
