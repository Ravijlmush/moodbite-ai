"""Concise NLG templates, starter pills, refinement chips, and crisis helpline resources."""

from __future__ import annotations

from app.schemas.api import CrisisResource

STARTER_QUICK_REPLY_PILLS: list[str] = [
    "Drained & tired",
    "Stressed, want spicy",
    "Bored, surprise me",
    "Light & fresh",
]

DEFAULT_REFINEMENT_CHIPS: list[str] = [
    "Under ₹250",
    "Make it spicier",
    "Something lighter",
    "Swap drink",
]

BUDGET_REFINEMENT_CHIPS: list[str] = [
    "Under ₹200",
    "Make it spicier",
    "Something lighter",
    "Swap drink",
]

LOADING_MICRO_COPY: list[str] = [
    "Reading the vibe...",
    "Checking fast kitchens near you...",
    "Pairing zero-mess combos...",
]

CRISIS_SUPPORT_MESSAGE = (
    "It sounds like you're carrying a really heavy moment right now, and I want you to be safe. "
    "Please reach out to someone who can support you right away:"
)

DISORDERED_EATING_SUPPORT_MESSAGE = (
    "You never deserve to be punished or go hungry—you matter, and it sounds like things feel overwhelming right now. "
    "I'm pausing food suggestions here so you can talk with someone who genuinely cares and can support you:"
)

HARMFUL_REFUSAL_MESSAGE = (
    "I can't help with anything poisonous, unsafe, or meant to harm someone. "
    "If you're feeling frustrated or angry and want safe, real comfort food instead, I'm here to help with that."
)

CRISIS_HELPLINES: list[CrisisResource] = [
    CrisisResource(
        name="Tele-MANAS (Govt. of India Mental Health Helpline)",
        contact="14416 / 1800-891-4416",
        availability="24/7 Toll-Free",
        region="India",
    ),
    CrisisResource(
        name="KIRAN National Helpline",
        contact="1800-599-0019",
        availability="24/7 Toll-Free",
        region="India",
    ),
    CrisisResource(
        name="iCall (TISS Psychosocial Helpline)",
        contact="9152987821",
        availability="Mon–Sat, 8 AM – 10 PM",
        region="India",
    ),
    CrisisResource(
        name="988 Suicide & Crisis Lifeline / International Directory",
        contact="Call or text 988 (US/CA) • findahelpline.com (Global)",
        availability="24/7 Free & Confidential",
        region="International",
    ),
]
