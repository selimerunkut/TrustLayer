import json
from unittest.mock import patch

from backend.services.circle_wallet import TransferReceipt

import pytest

from coverpilot_conversation.mock_backend import DraftStatus, MockBrokerBackend
from coverpilot_conversation.tools import build_broker_tools


def _ready_draft(backend: MockBrokerBackend) -> str:
    backend.mark_policy_research_done()
    draft = backend.prepare_budget_authorization(2.0, "Frankfurt to Bogota, Lufthansa")
    backend.confirm_budget_authorization(draft.draft_id, True)
    backend.pay_knowledge_service(draft.draft_id)
    backend.get_policy_recommendation(draft.draft_id, "Two-week Colombia trip")
    return draft.draft_id


def test_purchase_policy_funds_deployer_before_onchain(monkeypatch):
    monkeypatch.setenv("BASE_SEPOLIA_DEPLOYER_ADDRESS", "0xBA3330FB593dEb0203a5801B2E2f6f295f76FAd8")
    backend = MockBrokerBackend()
    draft_id = _ready_draft(backend)
    tools = {tool.name: tool for tool in build_broker_tools(backend)}
    purchase_tool = tools["purchase_policy"]

    fund_receipt = TransferReceipt(
        reference="fund",
        amount_usdc=1.0,
        destination_address="0xBA3330FB593dEb0203a5801B2E2f6f295f76FAd8",
        tx_hash="0xfund",
        attempted=True,
        provenance="circle:agent_wallet",
    )
    onchain_result = {
        "tx_hash": "0xdeadbeef",
        "premium_transfer_tx_hash": "0xdeadbeef",
        "premium_usdc": 1.0,
        "approve_tx_hashes": ["0xapprove"],
    }

    class FakeClient:
        def purchase_policy(self, **_kwargs):
            return onchain_result

    with patch("coverpilot_conversation.tools.ensure_broker_payer_usdc", return_value=fund_receipt) as fund:
        with patch("coverpilot_conversation.tools._try_build_chain_client", return_value=FakeClient()):
            raw = purchase_tool.invoke(
                {
                    "policy_draft_id": draft_id,
                    "customer_confirms_insurance_purchase": True,
                }
            )

    fund.assert_called_once_with(required_usdc=1.0)
    payload = json.loads(raw)
    assert payload["onchain"]["broker_funding"]["tx_hash"] == "0xfund"
    assert payload["onchain"]["tx_hash"] == "0xdeadbeef"


def test_purchase_policy_includes_onchain_payment_block(monkeypatch):
    monkeypatch.setenv("BASE_SEPOLIA_DEPLOYER_ADDRESS", "0xBA3330FB593dEb0203a5801B2E2f6f295f76FAd8")
    backend = MockBrokerBackend()
    draft_id = _ready_draft(backend)
    tools = {tool.name: tool for tool in build_broker_tools(backend)}
    purchase_tool = tools["purchase_policy"]

    mock_client = object()
    onchain_result = {
        "tx_hash": "0xdeadbeef",
        "premium_transfer_tx_hash": "0xdeadbeef",
        "premium_usdc": 1.0,
        "premium_vault_address": "0xBA3330FB593dEb0203a5801B2E2f6f295f76FAd8",
        "premium_transfer_method": "onchain_erc20_transferFrom",
        "approve_tx_hashes": ["0xapprove"],
        "block_explorer_url": "https://sepolia.basescan.org/tx/0xdeadbeef",
    }

    class FakeClient:
        def purchase_policy(self, **_kwargs):
            return onchain_result

    with patch("coverpilot_conversation.tools.ensure_broker_payer_usdc", return_value=None):
        with patch("coverpilot_conversation.tools._try_build_chain_client", return_value=FakeClient()):
            raw = purchase_tool.invoke(
                {
                    "policy_draft_id": draft_id,
                    "customer_confirms_insurance_purchase": True,
                }
            )

    payload = json.loads(raw)
    assert payload["premium_paid_usdc"] == 1.0
    assert payload["payment"]["attempted"] is True
    assert payload["payment"]["method"] == "onchain_erc20_transferFrom"
    assert payload["payment"]["tx_hash"] == "0xdeadbeef"
    assert payload["onchain"]["premium_transfer_tx_hash"] == "0xdeadbeef"
    assert backend.drafts[draft_id].status == DraftStatus.PURCHASED


def test_purchase_policy_without_prior_recommendation_synthesizes_rec(monkeypatch):
    """Demo safety net: LLM may skip get_policy_recommendation before purchase."""
    monkeypatch.setenv("BASE_SEPOLIA_DEPLOYER_ADDRESS", "0xBA3330FB593dEb0203a5801B2E2f6f295f76FAd8")
    backend = MockBrokerBackend()
    backend.mark_policy_research_done()
    draft = backend.prepare_budget_authorization(2.0, "Frankfurt to Bogota")
    backend.confirm_budget_authorization(draft.draft_id, True)
    backend.pay_knowledge_service(draft.draft_id)
    assert backend.drafts[draft.draft_id].status == DraftStatus.RESEARCH_PAID

    tools = {tool.name: tool for tool in build_broker_tools(backend)}
    raw = tools["purchase_policy"].invoke(
        {
            "policy_draft_id": draft.draft_id,
            "customer_confirms_insurance_purchase": True,
        }
    )
    payload = json.loads(raw)
    assert "error" not in payload
    assert payload["premium_paid_usdc"] == 1.0
    assert backend.drafts[draft.draft_id].status == DraftStatus.PURCHASED


def test_purchase_policy_recommendation_uses_one_usdc_premium():
    backend = MockBrokerBackend()
    backend.mark_policy_research_done()
    draft = backend.prepare_budget_authorization(2.0, "Small demo trip")
    backend.confirm_budget_authorization(draft.draft_id, True)
    backend.pay_knowledge_service(draft.draft_id)
    rec = backend.get_policy_recommendation(draft.draft_id, "Demo")
    assert rec["premiumUsdc"] == 1.0
    assert rec["payoutUsdc"] == 10.0
