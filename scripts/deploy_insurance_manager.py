#!/usr/bin/env python3
"""Create a burner deployer wallet and deploy InsuranceManager to Base Sepolia.

Usage:
  uv run scripts/deploy_insurance_manager.py create-wallet
  uv run scripts/deploy_insurance_manager.py deploy
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from eth_account import Account
from eth_tester import EthereumTester, PyEVMBackend
from solcx import compile_standard, install_solc, set_solc_version
from web3 import Web3
from web3.providers.eth_tester import EthereumTesterProvider


ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = ROOT / "contracts" / "InsuranceManager.sol"
ENV_PATH = ROOT / ".env"
SOLC_VERSION = "0.8.24"
CHAIN_ID = 84532


def load_env() -> None:
    load_dotenv(ENV_PATH)


def read_env_lines() -> list[str]:
    if not ENV_PATH.exists():
        return []
    return ENV_PATH.read_text().splitlines()


def upsert_env(key: str, value: str) -> None:
    lines = read_env_lines()
    rendered = f"{key}={value}"
    updated = False
    for idx, line in enumerate(lines):
        if line.startswith(f"{key}="):
            lines[idx] = rendered
            updated = True
            break
    if not updated:
        lines.append(rendered)
    ENV_PATH.write_text("\n".join(lines) + "\n")


def create_wallet() -> None:
    account = Account.create()
    private_key = f"0x{account.key.hex()}"
    print(f"address={account.address}")
    print(f"private_key={private_key}")
    upsert_env("BASE_SEPOLIA_DEPLOYER_ADDRESS", account.address)
    upsert_env("BASE_SEPOLIA_DEPLOYER_PRIVATE_KEY", private_key)
    print(f"saved_to={ENV_PATH}")


def compile_contract() -> tuple[list[dict[str, Any]], str]:
    source = CONTRACT_PATH.read_text()
    install_solc(SOLC_VERSION)
    set_solc_version(SOLC_VERSION)
    compiled = compile_standard(
        {
            "language": "Solidity",
            "sources": {"InsuranceManager.sol": {"content": source}},
            "settings": {
                "optimizer": {"enabled": True, "runs": 200},
                "viaIR": True,
                "outputSelection": {
                    "*": {
                        "*": ["abi", "evm.bytecode.object"],
                    }
                }
            },
        }
    )
    contract = compiled["contracts"]["InsuranceManager.sol"]["InsuranceManager"]
    return contract["abi"], contract["evm"]["bytecode"]["object"]


def build_deploy_tx(
    w3: Web3,
    account: Account,
    contract: Any,
    *,
    usdc_address: str,
    vault_address: str,
) -> dict[str, Any]:
    nonce = w3.eth.get_transaction_count(account.address)
    deploy_tx = {
        "from": account.address,
        "nonce": nonce,
    }
    chain_id = w3.eth.chain_id
    deploy_tx["chainId"] = chain_id

    constructor = contract.constructor(
        Web3.to_checksum_address(usdc_address),
        Web3.to_checksum_address(vault_address),
    )
    unsigned = constructor.build_transaction(deploy_tx)
    unsigned["gas"] = int(w3.eth.estimate_gas(unsigned) * 1.2)

    latest_block = w3.eth.get_block("latest")
    base_fee = latest_block.get("baseFeePerGas")
    if base_fee is not None:
        priority_fee = w3.to_wei(1, "gwei")
        unsigned["maxPriorityFeePerGas"] = priority_fee
        unsigned["maxFeePerGas"] = base_fee * 2 + priority_fee
    else:
        unsigned["gasPrice"] = w3.eth.gas_price
    return unsigned


def deploy_with_web3(w3: Web3, account: Account) -> str:
    load_env()
    usdc_address = os.environ.get("BASE_SEPOLIA_TEST_USDC_ADDRESS", "").strip()
    if not usdc_address:
        raise SystemExit("BASE_SEPOLIA_TEST_USDC_ADDRESS is missing")
    vault_address = (
        os.environ.get("TRUSTLAYER_PREMIUM_VAULT_ADDRESS", "").strip()
        or account.address
    )

    abi, bytecode = compile_contract()
    contract = w3.eth.contract(abi=abi, bytecode=bytecode)
    deploy_tx = build_deploy_tx(
        w3,
        account,
        contract,
        usdc_address=usdc_address,
        vault_address=vault_address,
    )
    signed = account.sign_transaction(deploy_tx)
    tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
    receipt = w3.eth.wait_for_transaction_receipt(tx_hash)

    if receipt.contractAddress is None:
        raise SystemExit("Deployment succeeded but no contract address was returned")

    print(json.dumps({
        "contract_address": receipt.contractAddress,
        "transaction_hash": tx_hash.hex(),
        "deployer_address": account.address,
    }, indent=2))
    return receipt.contractAddress


def deploy() -> None:
    load_env()
    rpc_url = os.environ.get("BASE_SEPOLIA_RPC_URL")
    private_key = os.environ.get("BASE_SEPOLIA_DEPLOYER_PRIVATE_KEY")

    if not rpc_url:
        raise SystemExit("BASE_SEPOLIA_RPC_URL is missing")
    if not private_key:
        raise SystemExit("BASE_SEPOLIA_DEPLOYER_PRIVATE_KEY is missing")

    account = Account.from_key(private_key)
    w3 = Web3(Web3.HTTPProvider(rpc_url))
    if not w3.is_connected():
        raise SystemExit(f"Could not connect to RPC: {rpc_url}")

    address = deploy_with_web3(w3, account)
    upsert_env("BASE_SEPOLIA_CONTRACT_ADDRESS", address)
    upsert_env("BASE_SEPOLIA_CHAIN_ID", str(CHAIN_ID))


def local_test() -> None:
    load_env()
    private_key = os.environ.get("BASE_SEPOLIA_DEPLOYER_PRIVATE_KEY")
    if not private_key:
        raise SystemExit("BASE_SEPOLIA_DEPLOYER_PRIVATE_KEY is missing")

    account = Account.from_key(private_key)
    eth_tester = EthereumTester(PyEVMBackend())
    w3 = Web3(EthereumTesterProvider(eth_tester))
    w3.eth.default_account = w3.eth.accounts[0]

    funding_tx = {
        "from": w3.eth.accounts[0],
        "to": account.address,
        "value": w3.to_wei(10, "ether"),
    }
    funding_hash = w3.eth.send_transaction(funding_tx)
    w3.eth.wait_for_transaction_receipt(funding_hash)

    address = deploy_with_web3(w3, account)
    print(json.dumps({
        "network": "eth-tester",
        "contract_address": address,
        "deployer_address": account.address,
        "funding_tx": funding_hash.hex(),
    }, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("create-wallet", help="Create a burner deployer wallet and save it to .env")
    sub.add_parser("deploy", help="Deploy InsuranceManager to Base Sepolia")
    sub.add_parser("local-test", help="Compile and deploy InsuranceManager on a local ephemeral chain")
    args = parser.parse_args()

    if args.command == "create-wallet":
        create_wallet()
    elif args.command == "deploy":
        deploy()
    elif args.command == "local-test":
        local_test()


if __name__ == "__main__":
    main()
