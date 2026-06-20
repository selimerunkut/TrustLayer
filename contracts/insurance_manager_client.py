"""Web3 client for the deployed InsuranceManager contract on Base Sepolia.

Usage:
    from contracts.insurance_manager_client import InsuranceManagerClient

    client = InsuranceManagerClient.from_env()
    result = client.purchase_policy(...)
    print(result["block_explorer_url"])
"""

from __future__ import annotations

import json
import os
import time
from typing import Any

from web3 import Web3

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

CHAIN_ID = 84532
USDC_DECIMALS = 6
BASESCAN_TX_URL = "https://sepolia.basescan.org/tx/{}"
BASESCAN_ADDR_URL = "https://sepolia.basescan.org/address/{}"

_POLICY_STATUS: dict[int, str] = {
    0: "Pending",
    1: "Active",
    2: "Rejected",
    3: "Refunded",
    4: "PayoutApproved",
    5: "PayoutPaid",
}

# Minimal ABI — only the functions and events this client calls.
# Derived from contracts/InsuranceManager.sol; keep in sync.
_ABI: list[dict[str, Any]] = [
    {
        "name": "purchasePolicy",
        "type": "function",
        "stateMutability": "nonpayable",
        "inputs": [
            {"name": "policyId", "type": "bytes32"},
            {"name": "customerWallet", "type": "address"},
            {"name": "budgetLockedUsdc", "type": "uint256"},
            {"name": "researchFeeUsdc", "type": "uint256"},
            {"name": "premiumUsdc", "type": "uint256"},
            {"name": "payoutUsdc", "type": "uint256"},
            {"name": "delayThresholdMinutes", "type": "uint256"},
            {"name": "policyStart", "type": "uint256"},
            {"name": "policyEnd", "type": "uint256"},
            {"name": "flightHash", "type": "bytes32"},
            {"name": "recommendationHash", "type": "bytes32"},
            {"name": "x402Reference", "type": "bytes32"},
        ],
        "outputs": [],
    },
    {
        "name": "policies",
        "type": "function",
        "stateMutability": "view",
        "inputs": [{"name": "", "type": "bytes32"}],
        "outputs": [
            {"name": "customerWallet", "type": "address"},
            {"name": "escrowedUsdc", "type": "uint256"},
            {"name": "refundUsdc", "type": "uint256"},
            {"name": "researchFeeUsdc", "type": "uint256"},
            {"name": "premiumUsdc", "type": "uint256"},
            {"name": "payoutUsdc", "type": "uint256"},
            {"name": "delayThresholdMinutes", "type": "uint256"},
            {"name": "policyStart", "type": "uint256"},
            {"name": "policyEnd", "type": "uint256"},
            {"name": "flightHash", "type": "bytes32"},
            {"name": "recommendationHash", "type": "bytes32"},
            {"name": "x402Reference", "type": "bytes32"},
            {"name": "status", "type": "uint8"},
        ],
    },
    {
        "name": "PolicyPurchased",
        "type": "event",
        "anonymous": False,
        "inputs": [
            {"name": "policyId", "type": "bytes32", "indexed": True},
            {"name": "customerWallet", "type": "address", "indexed": True},
            {"name": "escrowedUsdc", "type": "uint256", "indexed": False},
        ],
    },
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _str_to_bytes32(value: str) -> bytes:
    """Keccak-256 hash of a UTF-8 string → 32 bytes (suitable for bytes32 args)."""
    return Web3.keccak(text=value)


def _usdc_to_uint(amount_usdc: float) -> int:
    """Float USDC amount → uint256 with 6 decimal places."""
    return int(round(amount_usdc * 10**USDC_DECIMALS))


# ---------------------------------------------------------------------------
# Client
# ---------------------------------------------------------------------------


class InsuranceManagerClient:
    """Thin Web3 wrapper for InsuranceManager.sol deployed on Base Sepolia.

    All write calls are signed with the deployer private key stored in
    ``BASE_SEPOLIA_DEPLOYER_PRIVATE_KEY``. The deployer acts as the broker
    operator; customer wallet addresses are recorded on-chain for audit
    purposes but do not need to sign the transaction.
    """

    def __init__(
        self,
        rpc_url: str,
        contract_address: str,
        private_key: str,
        chain_id: int = CHAIN_ID,
    ) -> None:
        self._w3 = Web3(Web3.HTTPProvider(rpc_url))
        self._account = self._w3.eth.account.from_key(private_key)
        self._contract = self._w3.eth.contract(
            address=Web3.to_checksum_address(contract_address),
            abi=_ABI,
        )
        self._chain_id = chain_id

    # ------------------------------------------------------------------
    # Factory
    # ------------------------------------------------------------------

    @classmethod
    def from_env(cls) -> "InsuranceManagerClient":
        """Construct from environment variables (call after dotenv is loaded)."""
        return cls(
            rpc_url=os.environ["BASE_SEPOLIA_RPC_URL"],
            contract_address=os.environ["BASE_SEPOLIA_CONTRACT_ADDRESS"],
            private_key=os.environ["BASE_SEPOLIA_DEPLOYER_PRIVATE_KEY"],
            chain_id=int(os.environ.get("BASE_SEPOLIA_CHAIN_ID", str(CHAIN_ID))),
        )

    # ------------------------------------------------------------------
    # Status
    # ------------------------------------------------------------------

    def is_connected(self) -> bool:
        try:
            return self._w3.is_connected()
        except Exception:
            return False

    @property
    def operator_address(self) -> str:
        return self._account.address

    # ------------------------------------------------------------------
    # Write: purchasePolicy
    # ------------------------------------------------------------------

    def purchase_policy(
        self,
        *,
        policy_id: str,
        customer_wallet: str,
        budget_locked_usdc: float,
        research_fee_usdc: float,
        premium_usdc: float,
        payout_usdc: float,
        delay_threshold_minutes: int,
        policy_start_ts: int | None = None,
        policy_end_ts: int | None = None,
        flight_descriptor: str,
        recommendation_json: str,
        x402_receipt: str,
    ) -> dict[str, Any]:
        """Sign and broadcast purchasePolicy to Base Sepolia.

        Args:
            policy_id: Human-readable policy id (e.g. ``pol-abc123``). Hashed to bytes32.
            customer_wallet: Customer's EVM address recorded in the policy record.
            budget_locked_usdc: Maximum budget approved by the customer.
            research_fee_usdc: x402 research fee already paid.
            premium_usdc: Insurance premium deducted.
            payout_usdc: Maximum claim payout if delay is triggered.
            delay_threshold_minutes: Delay in minutes that triggers the payout.
            policy_start_ts: Coverage start as Unix timestamp (default: now).
            policy_end_ts: Coverage end as Unix timestamp (default: now + 7 days).
            flight_descriptor: Free-text trip summary used to derive flightHash.
            recommendation_json: JSON string of the recommendation for auditability.
            x402_receipt: x402 payment receipt id.

        Returns:
            Dict with ``tx_hash``, ``block_explorer_url``, ``status``, and onchain details.
        """
        now = int(time.time())
        start_ts = policy_start_ts if policy_start_ts is not None else now
        end_ts = policy_end_ts if policy_end_ts is not None else now + 7 * 86400

        policy_id_bytes = _str_to_bytes32(policy_id)
        flight_hash = _str_to_bytes32(flight_descriptor)
        rec_hash = _str_to_bytes32(recommendation_json)
        x402_ref = _str_to_bytes32(x402_receipt)

        customer_addr = Web3.to_checksum_address(customer_wallet)

        fn = self._contract.functions.purchasePolicy(
            policy_id_bytes,
            customer_addr,
            _usdc_to_uint(budget_locked_usdc),
            _usdc_to_uint(research_fee_usdc),
            _usdc_to_uint(premium_usdc),
            _usdc_to_uint(payout_usdc),
            delay_threshold_minutes,
            start_ts,
            end_ts,
            flight_hash,
            rec_hash,
            x402_ref,
        )

        nonce = self._w3.eth.get_transaction_count(self._account.address)
        latest = self._w3.eth.get_block("latest")
        base_fee = latest.get("baseFeePerGas") or self._w3.eth.gas_price
        priority = self._w3.to_wei(1, "gwei")

        tx = fn.build_transaction(
            {
                "from": self._account.address,
                "nonce": nonce,
                "chainId": self._chain_id,
                "maxFeePerGas": int(base_fee) * 2 + priority,
                "maxPriorityFeePerGas": priority,
            }
        )
        tx["gas"] = int(self._w3.eth.estimate_gas(tx) * 1.25)

        signed = self._account.sign_transaction(tx)
        tx_hash_bytes = self._w3.eth.send_raw_transaction(signed.raw_transaction)
        receipt = self._w3.eth.wait_for_transaction_receipt(tx_hash_bytes, timeout=90)

        tx_hex = tx_hash_bytes.hex()
        return {
            "tx_hash": tx_hex,
            "block_number": receipt["blockNumber"],
            "onchain_status": "success" if receipt["status"] == 1 else "reverted",
            "policy_id": policy_id,
            "policy_id_onchain_bytes32": "0x" + policy_id_bytes.hex(),
            "contract_address": self._contract.address,
            "chain": "base-sepolia",
            "block_explorer_url": BASESCAN_TX_URL.format(tx_hex),
            "contract_explorer_url": BASESCAN_ADDR_URL.format(self._contract.address),
        }

    # ------------------------------------------------------------------
    # Read: policies
    # ------------------------------------------------------------------

    def get_policy(self, policy_id: str) -> dict[str, Any]:
        """Read a policy record from the contract (view call, no gas cost).

        Args:
            policy_id: Human-readable policy id (same string used at purchase time).

        Returns:
            Dict with policy fields decoded from the contract, plus block explorer URLs.
        """
        policy_id_bytes = _str_to_bytes32(policy_id)
        rec = self._contract.functions.policies(policy_id_bytes).call()
        (
            customer_wallet,
            escrowed,
            refund,
            research_fee,
            premium,
            payout,
            delay_min,
            start_ts,
            end_ts,
            _flight_h,
            _rec_h,
            _x402_h,
            status_int,
        ) = rec

        found = customer_wallet != "0x0000000000000000000000000000000000000000"
        return {
            "found_onchain": found,
            "policy_id": policy_id,
            "policy_id_onchain_bytes32": "0x" + policy_id_bytes.hex(),
            "contract_address": self._contract.address,
            "customer_wallet": customer_wallet if found else None,
            "budget_locked_usdc": escrowed / 10**USDC_DECIMALS if found else None,
            "research_fee_usdc": research_fee / 10**USDC_DECIMALS if found else None,
            "premium_usdc": premium / 10**USDC_DECIMALS if found else None,
            "payout_usdc": payout / 10**USDC_DECIMALS if found else None,
            "delay_threshold_minutes": delay_min if found else None,
            "policy_start_ts": start_ts if found else None,
            "policy_end_ts": end_ts if found else None,
            "status": _POLICY_STATUS.get(status_int, str(status_int)) if found else "not_found",
            "chain": "base-sepolia",
            "contract_explorer_url": BASESCAN_ADDR_URL.format(self._contract.address),
        }
