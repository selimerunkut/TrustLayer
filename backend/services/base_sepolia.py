from dataclasses import dataclass
from typing import Mapping

from backend.schemas import OracleResolution, PolicyRecord


@dataclass(frozen=True)
class BaseSepoliaConfig:
    rpc_url: str
    contract_address: str
    test_usdc_address: str
    chain_id: int = 84532
    wallet_id: str = ""
    api_key: str = ""


def load_base_sepolia_config(env: Mapping[str, str]) -> BaseSepoliaConfig:
    return BaseSepoliaConfig(
        rpc_url=env.get("BASE_SEPOLIA_RPC_URL", "").strip(),
        contract_address=env.get("BASE_SEPOLIA_CONTRACT_ADDRESS", "").strip(),
        test_usdc_address=env.get("BASE_SEPOLIA_TEST_USDC_ADDRESS", "").strip(),
        wallet_id=env.get("CIRCLE_WALLET_ID", "").strip(),
        api_key=env.get("CIRCLE_API_KEY", "").strip(),
    )


def base_sepolia_ready(config: BaseSepoliaConfig) -> bool:
    return bool(config.rpc_url and config.contract_address and config.test_usdc_address)


def build_base_policy_created_artifact(
    policy: PolicyRecord,
    *,
    tx_hash: str,
    contract_address: str,
    chain_id: int = 84532,
    block_number: int | None = None,
    simulated: bool = False,
    provenance: str = "base:sepolia",
) -> dict[str, object]:
    artifact: dict[str, object] = {
        "policy_id": policy.policy_id,
        "contract_address": contract_address,
        "chain_id": chain_id,
        "tx_hash": tx_hash,
        "simulated": simulated,
        "provenance": provenance,
        "customer_wallet": policy.customer_wallet,
        "payout_usdc": policy.payout_usdc,
        "premium_usdc": policy.premium_usdc,
        "delay_threshold_minutes": policy.delay_threshold_minutes,
        "policy_start": policy.policy_start,
        "policy_end": policy.policy_end,
        "flight_hash": policy.flight_hash,
        "recommendation_hash": policy.recommendation_hash,
        "x402_reference": policy.x402_reference,
        "status": policy.status,
    }
    if block_number is not None:
        artifact["block_number"] = block_number
    return artifact


def build_claim_payout_receipt(
    *,
    policy_id: str,
    tx_hash: str,
    oracle_resolution: OracleResolution,
    contract_address: str,
    chain_id: int = 84532,
    block_number: int | None = None,
    simulated: bool = False,
    provenance: str = "base:sepolia",
) -> dict[str, object]:
    receipt: dict[str, object] = {
        "policy_id": policy_id,
        "contract_address": contract_address,
        "chain_id": chain_id,
        "tx_hash": tx_hash,
        "simulated": simulated,
        "provenance": provenance,
        "flight_hash": oracle_resolution.flight_hash,
        "arrived_on_time": oracle_resolution.arrived_on_time,
        "delay_minutes": oracle_resolution.delay_minutes,
        "observed_at": oracle_resolution.observed_at,
        "resolver_address": oracle_resolution.resolver_address,
    }
    if block_number is not None:
        receipt["block_number"] = block_number
    return receipt
