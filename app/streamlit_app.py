import logging
from dataclasses import dataclass

import streamlit as st

from backend.schemas import PolicyRecommendation
from backend.services.receipts import research_fee_usdc


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class CustomerFacingReceipt:
    headline: str
    summary_lines: tuple[str, ...]
    technical_details: tuple[tuple[str, str], ...]
    pool_selection_visible: bool = False
    simulated: bool = False
    provenance: str = ""


def build_non_insurance_disclaimer() -> str:
    return (
        "NOT LEGALLY VALID INSURANCE: this is a demo only, not a legally binding insurance product, "
        "and it may use mocked or degraded dependencies."
    )


def build_customer_facing_receipt(
    recommendation: PolicyRecommendation,
    *,
    simulated: bool = False,
    provenance: str = "",
) -> CustomerFacingReceipt:
    return CustomerFacingReceipt(
        headline=f"{recommendation.policy_name} — {recommendation.premium_usdc:.2f} USDC premium",
        summary_lines=(
            f"Payout if your flight is delayed {recommendation.delay_trigger_minutes} minutes or more: "
            f"{recommendation.payout_usdc:.2f} USDC",
            f"Coverage window: {recommendation.coverage_start} to {recommendation.coverage_end}",
            f"Why this fits: {recommendation.reason}",
        ),
        technical_details=(
            ("Coverage pool", recommendation.pool_id),
            ("Wallet", "hidden in customer view"),
            ("x402 reference", "hidden in customer view"),
            ("Recommendation hash", "hidden in customer view"),
        ),
        simulated=simulated,
        provenance=provenance,
    )


def build_fallback_banner(*, simulated: bool, provenance: str) -> str | None:
    if not simulated and not provenance:
        return None
    details = []
    if simulated:
        details.append("simulated")
    if provenance:
        details.append(provenance)
    return f"Fallback mode: {' / '.join(details)}"


def build_budget_quote_copy(max_budget_usdc: float) -> tuple[str, str]:
    fee_usdc = research_fee_usdc(max_budget_usdc)
    return (
        f"Maximum approved budget: {max_budget_usdc:.2f} USDC",
        f"Deterministic research-fee quote: {fee_usdc:.2f} USDC",
    )


def build_ui() -> None:
    st.title("CoverPilot MVP")
    st.caption("A plain-language travel-insurance demo for non-crypto-native travelers.")
    st.error(build_non_insurance_disclaimer())
    st.write("You describe the trip, we explain the coverage in plain language, and technical details stay hidden.")
    budget_line, fee_line = build_budget_quote_copy(100.0)
    st.info(budget_line)
    st.caption(fee_line)

    demo_recommendation = PolicyRecommendation(
        policy_name="Flight Delay Guard",
        premium_usdc=42.0,
        payout_usdc=300.0,
        delay_trigger_minutes=180,
        coverage_start="2026-06-20T00:00:00Z",
        coverage_end="2026-06-20T23:59:59Z",
        risk_tier="LOW",
        pool_id="pool-demo",
        reason="Matches the approved flight-delay demo profile.",
    )

    receipt = build_customer_facing_receipt(demo_recommendation)
    st.subheader(receipt.headline)
    for line in receipt.summary_lines:
        st.write(f"- {line}")
    fallback_banner = build_fallback_banner(simulated=receipt.simulated, provenance=receipt.provenance)
    if fallback_banner is not None:
        logger.info(fallback_banner)
        st.warning(fallback_banner)

    st.info("The app hides pool selection, wallet internals, and transaction plumbing from the traveler.")
    with st.expander("Technical details", expanded=False):
        for label, value in receipt.technical_details:
            st.write(f"**{label}:** {value}")


if __name__ == "__main__":
    build_ui()
