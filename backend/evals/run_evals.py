"""50-scenario Golden Dataset Evaluation Harness (Spec 08)."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from pathlib import Path
from typing import Any

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from app.agent.guardrails import verify_zero_hallucinations
from app.api.deps import build_container
from app.config import get_settings
from app.recommender.engine import item_is_allergy_safe, item_matches_dietary
from app.schemas.api import ChatTurnRequest, Location

SCENARIOS_PATH = Path(__file__).resolve().parent / "golden_scenarios.json"


def _percentile(sorted_vals: list[float], pct: float) -> float:
    if not sorted_vals:
        return 0.0
    idx = min(len(sorted_vals) - 1, max(0, int(round((pct / 100.0) * (len(sorted_vals) - 1)))))
    return sorted_vals[idx]


async def evaluate(use_judge: bool = False) -> dict[str, Any]:
    settings = get_settings()
    container = build_container(settings)
    scenarios = json.loads(SCENARIOS_PATH.read_text(encoding="utf-8"))
    assert len(scenarios) == 50, f"Expected 50 golden scenarios, got {len(scenarios)}"

    turn_latencies_ms: list[float] = []
    engine_latencies_ms: list[float] = []

    passed = 0
    dietary_violations = 0
    allergy_violations = 0
    hallucinations = 0
    turn_ceiling_failures = 0
    brevity_failures = 0
    crisis_failures = 0
    failures: list[dict[str, Any]] = []

    for idx, sc in enumerate(scenarios, start=1):
        sess_id = f"eval_{sc['id']}_{idx}"
        turns: list[str] = sc["turns"]
        expected = sc["expected"]
        last_resp = None

        for turn_num, msg in enumerate(turns, start=1):
            req = ChatTurnRequest(
                session_id=sess_id,
                user_id=f"eval_user_{idx}",
                message=msg,
                location=Location(),
            )
            t0 = time.perf_counter()
            resp = await container.orchestrator.handle_turn(req)
            elapsed = (time.perf_counter() - t0) * 1000.0
            turn_latencies_ms.append(elapsed)
            last_resp = resp

            if resp.action == "ask_followup" and len(resp.agent_message.split()) >= 45:
                brevity_failures += 1

            if resp.action == "recommend_combos":
                t_eng0 = time.perf_counter()
                _ = container.engine.recommend(resp.full_context, Location(), user_message=msg, limit=4)
                engine_latencies_ms.append((time.perf_counter() - t_eng0) * 1000.0)

        assert last_resp is not None
        sc_errors: list[str] = []

        if expected.get("action") == "crisis_support":
            if last_resp.action != "crisis_support" or last_resp.recommendations or not last_resp.crisis_resources:
                crisis_failures += 1
                sc_errors.append("crisis_guardrail_failed")
        else:
            if last_resp.action != "recommend_combos":
                turn_ceiling_failures += 1
                sc_errors.append(f"expected recommend_combos, got {last_resp.action}")

            min_combos = expected.get("min_combos", 3)
            if len(last_resp.recommendations) < min_combos:
                sc_errors.append(f"expected >= {min_combos} combos, got {len(last_resp.recommendations)}")

            if expected.get("max_eta_mins"):
                for rec in last_resp.recommendations:
                    if rec.restaurant.eta_mins > expected["max_eta_mins"]:
                        sc_errors.append(f"eta {rec.restaurant.eta_mins} > {expected['max_eta_mins']}")

            if expected.get("max_budget_inr"):
                for rec in last_resp.recommendations:
                    if rec.total_price_inr > expected["max_budget_inr"]:
                        sc_errors.append(f"price {rec.total_price_inr} > {expected['max_budget_inr']}")

            exp_diet = expected.get("dietary_type")
            if exp_diet:
                for rec in last_resp.recommendations:
                    for item in rec.items:
                        db_item = container.catalog.get_item(item.item_id)
                        if db_item is None or not item_matches_dietary(db_item, exp_diet):
                            dietary_violations += 1
                            sc_errors.append(f"dietary_violation:{item.item_id}")

            for allergy in expected.get("allergies", []):
                for rec in last_resp.recommendations:
                    for item in rec.items:
                        db_item = container.catalog.get_item(item.item_id)
                        if db_item is None or not item_is_allergy_safe(db_item, [allergy], []):
                            allergy_violations += 1
                            sc_errors.append(f"allergy_violation:{allergy}:{item.item_id}")

            verified = verify_zero_hallucinations(
                last_resp.recommendations, container.catalog, last_resp.full_context
            )
            if len(verified) != len(last_resp.recommendations):
                hallucinations += 1
                sc_errors.append("hallucinated_or_invalid_combo")

        if not sc_errors:
            passed += 1
        else:
            failures.append({"id": sc["id"], "errors": sc_errors})

    turn_latencies_ms.sort()
    engine_latencies_ms.sort()

    summary = {
        "total_scenarios": len(scenarios),
        "passed": passed,
        "failed": len(failures),
        "pass_rate_pct": round((passed / len(scenarios)) * 100.0, 2),
        "dietary_violation_rate_pct": round((dietary_violations / len(scenarios)) * 100.0, 2),
        "allergy_violations": allergy_violations,
        "hallucinations": hallucinations,
        "turn_ceiling_failures": turn_ceiling_failures,
        "brevity_failures": brevity_failures,
        "crisis_failures": crisis_failures,
        "p95_turn_latency_ms": round(_percentile(turn_latencies_ms, 95.0), 2),
        "p99_engine_latency_ms": round(_percentile(engine_latencies_ms, 99.0), 2),
        "llm_provider": settings.resolved_llm_provider(),
        "judge_enabled": use_judge and settings.resolved_llm_provider() in ("openai", "gemini"),
        "failures": failures,
    }
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Run MoodBite AI 50-scenario evaluation suite.")
    parser.add_argument("--judge", action="store_true", help="Enable optional LLM-as-a-Judge scoring if API key is set.")
    args = parser.parse_args()
    report = asyncio.run(evaluate(use_judge=args.judge))
    print(json.dumps(report, indent=2, ensure_ascii=False))
    if report["failed"] > 0 or report["p99_engine_latency_ms"] >= 120.0 or report["p95_turn_latency_ms"] >= 1800.0:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
