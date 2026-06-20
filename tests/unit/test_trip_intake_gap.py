"""Unit tests for ``trip_intake_gap`` deterministic intake rules."""

from coverpilot_conversation.trip_intake_gap import evaluate_trip_intake


def test_policy_chile_only_message_not_ready():
    """Vague 'trip to Chile' should block until origin, dates, and worries are captured."""
    r = evaluate_trip_intake(
        "policy_research",
        depart_from="",
        arrive_to="Chile",
        travel_dates="",
        airlines_routes_layovers="",
        travelers="",
        worries_delay_cancel="",
        max_budget_usdc_hint="",
    )
    assert r["ready"] is False
    assert r["primary_question"]
    keys = [m["key"] for m in r["missing_blocking"]]
    assert "depart_from" in keys
    assert "travel_dates" in keys
    assert "worries_delay_cancel" in keys


def test_policy_ready_when_blocking_slots_filled():
    r = evaluate_trip_intake(
        "policy_research",
        depart_from="Sofia",
        arrive_to="Santiago Chile",
        travel_dates="June 27 out, July 7 back",
        airlines_routes_layovers="",
        travelers="",
        worries_delay_cancel="delays and cancellations",
        max_budget_usdc_hint="",
    )
    assert r["ready"] is True
    assert r["primary_question"] is None
    assert r["missing_recommended"]


def test_prepare_requires_budget_digits():
    r = evaluate_trip_intake(
        "prepare_budget_authorization",
        depart_from="Berlin",
        arrive_to="Santiago",
        travel_dates="July",
        airlines_routes_layovers="",
        travelers="",
        worries_delay_cancel="delays",
        max_budget_usdc_hint="",
    )
    assert r["ready"] is False
    assert any(m["key"] == "max_budget_usdc_hint" for m in r["missing_blocking"])

    r2 = evaluate_trip_intake(
        "prepare_budget_authorization",
        depart_from="Berlin",
        arrive_to="Santiago",
        travel_dates="July",
        airlines_routes_layovers="",
        travelers="",
        worries_delay_cancel="delays",
        max_budget_usdc_hint="45 USDC from CRM usual_coverage_budget_usdc",
    )
    assert r2["ready"] is True
