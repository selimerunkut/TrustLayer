"""Deterministic trip intake checks for the broker agent (no LLM).

Used by ``trip_intake_gap_check`` so Betty asks clarifying questions before
``policy_research`` / ``prepare_budget_authorization`` when required slots are empty.
"""

from __future__ import annotations

import re
from typing import Any, Literal

ForStep = Literal["policy_research", "prepare_budget_authorization"]

# Questions must stay short; Betty turns them into natural language.
BLOCKING_QUESTIONS: dict[str, str] = {
    "depart_from": "Which city or airport are you leaving from?",
    "arrive_to": "Which city or airport are you flying to (not just the country)?",
    "travel_dates": "What are your outbound and return dates, or at least the week or month you're traveling?",
    "worries_delay_cancel": "What do you want protection for most: long delays, cancellations, missed connections, or a bit of everything?",
}

RECOMMENDED_QUESTIONS: dict[str, str] = {
    "airlines_routes_layovers": "Have you already booked flights? If so, which airlines and any layovers or connection cities?",
    "travelers": "How many travelers should this cover (just you or a group)?",
}

_PREPARE_BUDGET_QUESTION = (
    "What maximum amount in USDC are you comfortable spending on this protection "
    "(or confirm the amount if we suggested one from your profile)?"
)


def _meaningful(s: str) -> bool:
    t = (s or "").strip().lower()
    if len(t) < 2:
        return False
    if t in ("unknown", "n/a", "na", "tbd", "not sure", "unsure", "no idea", "?", "idk"):
        return False
    if re.fullmatch(r"[\s\-_,.]+", t):
        return False
    return True


def _has_budget_number(s: str) -> bool:
    """True if the traveler (or CRM hint passed by the model) includes some numeric budget."""
    return bool(re.search(r"\d", (s or "").strip()))


def evaluate_trip_intake(
    for_step: ForStep,
    depart_from: str,
    arrive_to: str,
    travel_dates: str,
    airlines_routes_layovers: str,
    travelers: str,
    worries_delay_cancel: str,
    max_budget_usdc_hint: str,
) -> dict[str, Any]:
    """Return gap analysis for the next broker tool step.

    The model fills each field with text taken from the conversation (or CRM tool JSON).
    Empty string means unknown.
    """
    fields = {
        "depart_from": depart_from,
        "arrive_to": arrive_to,
        "travel_dates": travel_dates,
        "worries_delay_cancel": worries_delay_cancel,
        "airlines_routes_layovers": airlines_routes_layovers,
        "travelers": travelers,
        "max_budget_usdc_hint": max_budget_usdc_hint,
    }

    missing_blocking: list[dict[str, str]] = []
    for key in ("depart_from", "arrive_to", "travel_dates", "worries_delay_cancel"):
        if not _meaningful(fields[key]):
            missing_blocking.append({"key": key, "question": BLOCKING_QUESTIONS[key]})

    missing_recommended: list[dict[str, str]] = []
    for key in ("airlines_routes_layovers", "travelers"):
        if not _meaningful(fields[key]):
            missing_recommended.append({"key": key, "question": RECOMMENDED_QUESTIONS[key]})

    ready_policy = len(missing_blocking) == 0

    budget_ok = _has_budget_number(max_budget_usdc_hint)
    missing_budget = not budget_ok

    if for_step == "policy_research":
        ready = ready_policy
        primary_question = missing_blocking[0]["question"] if missing_blocking else None
        if ready and missing_recommended:
            note_recommended = (
                "Optional: you may ask one short follow-up for airlines/layovers or traveler count "
                "before or after policy_research to improve the digest — not required to run the tool."
            )
        else:
            note_recommended = None
        return {
            "for_step": for_step,
            "ready": ready,
            "missing_blocking": missing_blocking,
            "missing_recommended": missing_recommended,
            "primary_question": primary_question,
            "note": note_recommended,
            "hints": (
                "Fill each argument from the user's words or from lookup_customer_profile JSON "
                "(e.g. usual_coverage_budget_usdc → max_budget_usdc_hint). "
                "Do not leave worries_delay_cancel blank if they mentioned delays or cancellations."
            ),
        }

    # prepare_budget_authorization: need KB-ready trip facts + a numeric budget cap.
    missing: list[dict[str, str]] = list(missing_blocking)
    if missing_budget:
        missing.append({"key": "max_budget_usdc_hint", "question": _PREPARE_BUDGET_QUESTION})

    ready = ready_policy and budget_ok
    if not ready:
        primary = missing[0]["question"]
    else:
        primary = None

    return {
        "for_step": for_step,
        "ready": ready,
        "missing_blocking": missing,
        "missing_recommended": missing_recommended if ready_policy else [],
        "primary_question": primary,
        "note": (
            "Call only after policy_research has succeeded for this session. "
            "Ensure trip_summary matches the filled fields."
        )
        if ready
        else None,
        "hints": (
            "For budget, pass digits from the traveler or CRM (e.g. '45 USDC from profile')."
        ),
    }
