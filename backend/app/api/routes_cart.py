"""Cart management endpoints for one-click + ADD COMBO TO CART."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import AppContainer, get_container
from app.schemas.api import AddToCartRequest, CartEntry, CartResponse

router = APIRouter(prefix="/api/v1/cart", tags=["cart"])


def _build_cart_response(session_id: str, entries: list[CartEntry]) -> CartResponse:
    return CartResponse(
        session_id=session_id,
        items=entries,
        total_items=sum(e.quantity for e in entries),
        total_price_inr=sum(e.line_total_inr for e in entries),
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
        # Validate submitted combo items against authoritative catalog before accepting
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
