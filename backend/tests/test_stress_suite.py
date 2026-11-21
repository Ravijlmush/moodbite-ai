"""Regression pytest suite covering all 30 safety, injection, messy-input, conflict & load stress cases."""

from __future__ import annotations

import asyncio

from evals.run_stress_suite import run_stress_suite


def test_full_30_prompt_stress_suite_passes_all_axes() -> None:
    report = asyncio.run(run_stress_suite())
    assert report["total_prompts"] == 30
    assert report["safety_failures"] == 0
    assert report["all_1_to_6_and_10_safe"] is True
    assert report["failed"] == 0, f"Failed stress cases: {[r for r in report['results'] if r['overall'] != 'PASS']}"
