import pytest

from coverpilot_conversation.kb_policy_research import run_policy_research
from coverpilot_conversation.mock_backend import DraftStatus, MockBrokerBackend


def test_prepare_budget_requires_policy_research_first():
    b = MockBrokerBackend()
    with pytest.raises(ValueError, match="policy_research"):
        b.prepare_budget_authorization(100.0, "Berlin to Bogotá via London")
    b.mark_policy_research_done()
    d = b.prepare_budget_authorization(100.0, "Berlin to Bogotá via London")
    assert d.draft_id.startswith("draft-")


def test_get_policy_recommendation_without_prior_payment_coalesces_pay():
    """Demo safety net: LLM may skip pay_knowledge_research_fee before get_policy_recommendation."""
    b = MockBrokerBackend()
    b.mark_policy_research_done()
    d = b.prepare_budget_authorization(45.0, "Sofia–Frankfurt–Santiago")
    b.confirm_budget_authorization(d.draft_id, True)
    assert b.drafts[d.draft_id].status == DraftStatus.AUTHORIZED

    rec = b.get_policy_recommendation(d.draft_id, "Sofia–Frankfurt–Santiago")
    assert rec["premiumUsdc"] > 0
    assert b.drafts[d.draft_id].status == DraftStatus.RECOMMENDED
    assert b.drafts[d.draft_id].x402_receipt


def test_get_policy_status_accepts_draft_id():
    """Demo safety net: LLM may pass policy_draft_id instead of pol-... id."""
    b = MockBrokerBackend()
    b.mark_policy_research_done()
    d = b.prepare_budget_authorization(45.0, "Sofia–Frankfurt–Santiago")
    b.confirm_budget_authorization(d.draft_id, True)
    status = b.get_policy_status(d.draft_id)
    assert status["policy_draft_id"] == d.draft_id
    assert status["policy_id"] is None
    assert status["status"] == DraftStatus.AUTHORIZED.value


def test_confirm_budget_authorization_idempotent_after_recommendation():
    """LLM may re-call confirm after get_policy_recommendation coalesced earlier steps."""
    b = MockBrokerBackend()
    b.mark_policy_research_done()
    d = b.prepare_budget_authorization(45.0, "Sofia–Frankfurt–Santiago")
    b.get_policy_recommendation(d.draft_id, "Sofia–Frankfurt–Santiago")
    assert b.drafts[d.draft_id].status == DraftStatus.RECOMMENDED

    confirmed = b.confirm_budget_authorization(d.draft_id, True)
    assert confirmed.status == DraftStatus.RECOMMENDED


def test_pay_knowledge_authorizes_when_draft_still_budget_prepared():
    """LLM sometimes skips confirm_budget_authorization; payment after explicit fee consent coalesces."""
    b = MockBrokerBackend()
    b.mark_policy_research_done()
    d = b.prepare_budget_authorization(45.0, "Sofia–Frankfurt–Santiago")
    assert d.status == DraftStatus.BUDGET_PREPARED
    receipt = b.pay_knowledge_service(d.draft_id)
    assert d.status == DraftStatus.RESEARCH_PAID
    assert receipt["paid_usdc"] == d.research_fee_usdc
    assert receipt["x402_receipt"]


def test_pay_knowledge_idempotent_when_recommendation_already_paid():
    """LLM may call pay after get_policy_recommendation coalesced payment (no double debit)."""
    b = MockBrokerBackend()
    b.mark_policy_research_done()
    d = b.prepare_budget_authorization(45.0, "Sofia–Frankfurt–Santiago")
    b.confirm_budget_authorization(d.draft_id, True)
    b.get_policy_recommendation(d.draft_id, "Sofia–Frankfurt–Santiago")
    assert b.drafts[d.draft_id].status == DraftStatus.RECOMMENDED
    wallet_after_first = b.broker_wallet_usdc
    receipt2 = b.pay_knowledge_service(d.draft_id)
    assert b.broker_wallet_usdc == wallet_after_first
    assert receipt2.get("note", "").startswith("Research fee was already")
    assert receipt2["x402_receipt"] == b.drafts[d.draft_id].x402_receipt


def test_policy_research_returns_kb_shape():
    r = run_policy_research("Ryanair London layover Bogotá delay fear")
    assert r["kb_relative_path"] == "KB/flight_attributes.md"
    assert "mock_subtool_trace" in r
    assert "eu261_germany" in r["excerpts"]
    assert "EU Regulation 261" in r["excerpts"]["eu261_germany"]
    assert "colombia_rac3" in r["excerpts"]
    assert "germany_colombia_route_examples" in r["excerpts"]
    assert "Brazil" in r["narration_scope"]["do_not_tour_unless_in_excerpts"]


def test_colombia_only_omits_other_sa_jurisdictions_excerpt():
    r = run_policy_research("Trip to Colombia Bogotá flight delay insurance")
    assert "other_south_american_jurisdictions" not in r["excerpts"]
    assert "eu261_germany" not in r["excerpts"]
    blob = "\n".join(r["excerpts"].values())
    assert "Brazil (ANAC)" not in blob
    assert "RAC 3" in r["excerpts"]["colombia_rac3"]
    assert "Brazil" in r["narration_scope"]["do_not_tour_unless_in_excerpts"]


def test_chile_named_includes_other_sa_excerpt():
    r = run_policy_research("Santiago Chile to Berlin delay")
    assert "other_south_american_jurisdictions" in r["excerpts"]
    assert "Chile" in r["excerpts"]["other_south_american_jurisdictions"]
