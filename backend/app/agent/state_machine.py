"""Conversational State Machine Orchestrator (Specs 02, 03, 06 & 07)."""

from __future__ import annotations

import time
from typing import Literal

from app.agent.guardrails import (
    build_context_summary,
    detect_crisis,
    get_crisis_response,
    merge_and_lock_constraints,
    sanitize_reply_and_pills,
    verify_zero_hallucinations,
)
from app.agent.heuristic_extractor import extract_offline_turn
from app.agent.llm_client import LLMClient, LLMFallbackTriggered
from app.agent.nlg import build_recommendation_intro
from app.config import Settings
from app.prompts.templates import BUDGET_REFINEMENT_CHIPS, DEFAULT_REFINEMENT_CHIPS
from app.recommender.catalog_repo import CatalogRepository
from app.recommender.engine import RecommendationEngine
from app.recommender.refiner import apply_refinement_chip
from app.schemas.api import ChatRefineRequest, ChatTurnRequest, ChatTurnResponse
from app.schemas.context import UserContext
from app.storage.session_store import SessionStore


class MoodBiteOrchestrator:
    """Hybrid state machine: LLM/heuristic empathy & extraction + deterministic combo engine."""

    def __init__(
        self,
        *,
        settings: Settings,
        session_store: SessionStore,
        catalog: CatalogRepository,
        engine: RecommendationEngine,
        llm_client: LLMClient | None = None,
    ) -> None:
        self.settings = settings
        self.session_store = session_store
        self.catalog = catalog
        self.engine = engine
        self.llm_client = llm_client or LLMClient(settings)

    async def handle_turn(self, request: ChatTurnRequest) -> ChatTurnResponse:
        t0 = time.perf_counter()
        session = await self.session_store.get_or_create(request.session_id)
        prev_context = session.user_context.model_copy(deep=True)
        prev_context.session_id = request.session_id
        prev_context.turn_count += 1

        # 1. Crisis safety guardrail (must run before any food routing)
        if detect_crisis(request.message):
            session.append_turn("user", request.message)
            resp = get_crisis_response(request.session_id, prev_context.turn_count, prev_context)
            session.user_context = resp.full_context
            session.last_recommendations = []
            session.append_turn("assistant", resp.agent_message)
            await self.session_store.save(session)
            resp.latency_ms = round((time.perf_counter() - t0) * 1000.0, 2)
            return resp

        # Apply active UI filters immediately on the working context
        working_ctx = prev_context.model_copy(deep=True)
        if request.active_filters.dietary_type is not None:
            if request.active_filters.dietary_type != "any":
                working_ctx.hard_constraints.dietary_type = request.active_filters.dietary_type
        if request.active_filters.max_budget_inr is not None:
            working_ctx.hard_constraints.max_budget_inr = request.active_filters.max_budget_inr

        # 2. Extract state via external LLM (if configured) or offline heuristic extractor
        provider = self.settings.resolved_llm_provider()
        llm_mode: Literal[
            "openrouter", "openai", "gemini", "ollama", "offline", "deterministic_fallback", "crisis_guardrail"
        ] = provider
        used_fallback = False

        if provider in ("openrouter", "openai", "gemini", "ollama"):
            try:
                extracted = await self.llm_client.extract_turn(
                    provider=provider,
                    current_context=working_ctx,
                    chat_history=session.chat_history,
                    user_message=request.message,
                )
            except LLMFallbackTriggered:
                # Spec 07: timeout >2.5s or schema failure -> deterministic comfort_fast fallback
                used_fallback = True
                llm_mode = "deterministic_fallback"
                fallback_ctx = working_ctx.model_copy(deep=True)
                fallback_ctx.user_state.primary_mood = "tired_and_down"
                fallback_ctx.user_state.energy_level = "low"
                fallback_ctx.food_preferences.effort_to_eat = "zero_mess"
                fallback_ctx.food_preferences.craving_profiles = [
                    "warm_comfort",
                    "comfort_classic",
                    "fizzy_sweet_kick",
                ]
                fallback_ctx.hard_constraints.max_eta_mins = min(
                    fallback_ctx.hard_constraints.max_eta_mins, 30
                )
                fallback_ctx.routing.state_confidence = 0.85
                fallback_ctx.routing.next_action = "recommend_combos"
                extracted_ctx = merge_and_lock_constraints(
                    prev_context, fallback_ctx, request.message, request.active_filters
                )
                reply_text = ""
                pills = list(DEFAULT_REFINEMENT_CHIPS)
            else:
                extracted_ctx = merge_and_lock_constraints(
                    prev_context,
                    extracted.updated_context,
                    request.message,
                    request.active_filters,
                )
                reply_text = extracted.reply_text
                pills = extracted.quick_reply_pills
        else:
            llm_mode = "offline"
            extracted = extract_offline_turn(working_ctx, request.message)
            extracted_ctx = merge_and_lock_constraints(
                prev_context,
                extracted.updated_context,
                request.message,
                request.active_filters,
            )
            reply_text = extracted.reply_text
            pills = extracted.quick_reply_pills

        # 3. Decision Gate: confidence >= 0.75 OR turn >= 3 forces recommend_combos
        should_recommend = (
            extracted_ctx.routing.next_action == "recommend_combos"
            or extracted_ctx.routing.state_confidence >= 0.75
            or extracted_ctx.turn_count >= 3
        )

        recommendations = []
        if should_recommend:
            extracted_ctx.routing.next_action = "recommend_combos"
            extracted_ctx.routing.clarifying_question = None
            raw_recs = self.engine.recommend(
                context=extracted_ctx,
                location=request.location,
                user_message=request.message,
                limit=4,
                swap_drink_step=0,
            )
            recommendations = verify_zero_hallucinations(raw_recs, self.catalog, extracted_ctx)

            # Safe non-dietary fallback if tight budget/ETA produced fewer than 3 combos
            if len(recommendations) < 3 and extracted_ctx.hard_constraints.max_budget_inr is not None:
                # Only loosen budget cap slightly? No — preserve user's budget unless zero results,
                # wait: never violate user's hard constraints! Keep verified matches as-is.
                pass

            if not recommendations:
                intro = (
                    "Nothing matched every strict filter at once nearby—try clearing a budget "
                    "or dietary chip below to see fast combos:"
                )
            else:
                intro = build_recommendation_intro(
                    extracted_ctx,
                    len(recommendations),
                    used_fallback=used_fallback,
                )

            ref_chips = (
                list(BUDGET_REFINEMENT_CHIPS)
                if extracted_ctx.hard_constraints.max_budget_inr and extracted_ctx.hard_constraints.max_budget_inr <= 250
                else list(DEFAULT_REFINEMENT_CHIPS)
            )
            clean_reply, clean_pills = sanitize_reply_and_pills(
                intro, ref_chips, enforce_45_word_limit=False
            )
            session.swap_drink_step = 0
            session.last_recommendations = recommendations
        else:
            extracted_ctx.routing.next_action = "ask_followup"
            clean_reply, clean_pills = sanitize_reply_and_pills(
                reply_text, pills, enforce_45_word_limit=True
            )

        session.user_context = extracted_ctx
        session.append_turn("user", request.message)
        session.append_turn("assistant", clean_reply)
        await self.session_store.save(session)

        latency_ms = round((time.perf_counter() - t0) * 1000.0, 2)
        return ChatTurnResponse(
            session_id=request.session_id,
            turn_count=extracted_ctx.turn_count,
            action=extracted_ctx.routing.next_action,
            agent_message=clean_reply,
            user_context=build_context_summary(extracted_ctx),
            full_context=extracted_ctx,
            recommendations=recommendations,
            quick_reply_pills=clean_pills,
            crisis_resources=[],
            latency_ms=latency_ms,
            llm_mode=llm_mode,
        )

    async def handle_refine(self, request: ChatRefineRequest) -> ChatTurnResponse:
        t0 = time.perf_counter()
        session = await self.session_store.get_or_create(request.session_id)
        base_ctx = session.user_context.model_copy(deep=True)
        base_ctx.session_id = request.session_id
        if base_ctx.turn_count == 0:
            base_ctx.turn_count = 1

        if request.active_filters is not None:
            if request.active_filters.dietary_type is not None:
                base_ctx.hard_constraints.dietary_type = request.active_filters.dietary_type
            if request.active_filters.max_budget_inr is not None:
                base_ctx.hard_constraints.max_budget_inr = request.active_filters.max_budget_inr

        refined_ctx, new_swap_step, intro = apply_refinement_chip(
            base_ctx,
            request.chip,
            session.swap_drink_step,
        )

        raw_recs = self.engine.recommend(
            context=refined_ctx,
            location=request.location,
            user_message=request.chip,
            limit=4,
            swap_drink_step=new_swap_step,
        )
        recommendations = verify_zero_hallucinations(raw_recs, self.catalog, refined_ctx)

        ref_chips = (
            list(BUDGET_REFINEMENT_CHIPS)
            if refined_ctx.hard_constraints.max_budget_inr and refined_ctx.hard_constraints.max_budget_inr <= 250
            else list(DEFAULT_REFINEMENT_CHIPS)
        )
        clean_reply, clean_pills = sanitize_reply_and_pills(
            intro, ref_chips, enforce_45_word_limit=False
        )

        session.user_context = refined_ctx
        session.swap_drink_step = new_swap_step
        session.last_recommendations = recommendations
        session.append_turn("user", f"[Refine: {request.chip}]")
        session.append_turn("assistant", clean_reply)
        await self.session_store.save(session)

        latency_ms = round((time.perf_counter() - t0) * 1000.0, 2)
        provider = self.settings.resolved_llm_provider()
        return ChatTurnResponse(
            session_id=request.session_id,
            turn_count=refined_ctx.turn_count,
            action="recommend_combos",
            agent_message=clean_reply,
            user_context=build_context_summary(refined_ctx),
            full_context=refined_ctx,
            recommendations=recommendations,
            quick_reply_pills=clean_pills,
            crisis_resources=[],
            latency_ms=latency_ms,
            llm_mode=provider,
        )
