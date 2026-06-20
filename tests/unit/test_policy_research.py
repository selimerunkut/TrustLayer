import pytest

from coverpilot_conversation.kb_policy_research import run_policy_research
from coverpilot_conversation.mock_backend import MockBrokerBackend


def test_prepare_budget_requires_policy_research_first():
    b = MockBrokerBackend()
    with pytest.raises(ValueError, match="policy_research"):
        b.prepare_budget_authorization(100.0, "Berlin to Bogotá via London")
    b.mark_policy_research_done()
    d = b.prepare_budget_authorization(100.0, "Berlin to Bogotá via London")
    assert d.draft_id.startswith("draft-")


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
