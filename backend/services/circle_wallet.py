"""Broker wallet balance, transaction history, and premium USDC transfers."""

from __future__ import annotations

import json
import logging
import os
import re
import shutil
import subprocess
import time
import uuid
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

import httpx
from web3 import Web3

from backend.schemas import (
    SessionMode,
    WalletBalanceResponse,
    WalletTokenBalance,
    WalletTransactionItem,
    WalletTransactionsResponse,
)
from backend.services.base_sepolia import (
    blockscout_tx_url,
    load_base_sepolia_config,
)
from backend.services.session_mode import preflight_session_mode

logger = logging.getLogger(__name__)

MOCK_WALLET_USDC = 10_000.0
MOCK_PROVENANCE = "mock:circle_wallet"
W3S_PROVENANCE = "circle:w3s"
ONCHAIN_PROVENANCE = "base:sepolia:erc20"
CLI_PROVENANCE = "circle:cli"
TRANSFER_PROVENANCE = "circle:agent_wallet"
CIRCLE_API_BASE = "https://api.circle.com"
USDC_DECIMALS = 6
UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
    re.IGNORECASE,
)

ERC20_BALANCE_OF_ABI = [
    {
        "constant": True,
        "inputs": [{"name": "account", "type": "address"}],
        "name": "balanceOf",
        "outputs": [{"name": "", "type": "uint256"}],
        "type": "function",
    }
]


class CircleWalletError(RuntimeError):
    """Raised when a live Circle wallet request fails."""


@dataclass(frozen=True)
class TransferReceipt:
    reference: str
    amount_usdc: float
    destination_address: str
    tx_hash: str = ""
    simulated: bool = False
    provenance: str = ""
    attempted: bool = False
    error: str = ""


def circle_w3s_configured(env: Mapping[str, str] | None = None) -> bool:
    current = _env(env)
    return bool(current.get("CIRCLE_API_KEY", "").strip() and current.get("CIRCLE_WALLET_ID", "").strip())


def resolve_base_sepolia_usdc_address(env: Mapping[str, str] | None = None) -> str:
    return load_base_sepolia_config(_env(env)).test_usdc_address


def resolve_premium_vault_address(env: Mapping[str, str] | None = None) -> str:
    current = _env(env)
    explicit = current.get("TRUSTLAYER_PREMIUM_VAULT_ADDRESS", "").strip()
    if explicit:
        return explicit
    fallback = current.get("BASE_SEPOLIA_DEPLOYER_ADDRESS", "").strip()
    if fallback:
        return fallback
    raise CircleWalletError("TRUSTLAYER_PREMIUM_VAULT_ADDRESS or BASE_SEPOLIA_DEPLOYER_ADDRESS is not set.")


def resolve_agent_wallet_address(env: Mapping[str, str] | None = None) -> str:
    current = _env(env)
    wallet_id = current.get("CIRCLE_WALLET_ID", "").strip()
    if _is_eth_address(wallet_id):
        return Web3.to_checksum_address(wallet_id)
    listed = _lookup_agent_wallet_address_from_cli(current)
    if listed:
        return Web3.to_checksum_address(listed)
    raise CircleWalletError(
        "CIRCLE_WALLET_ID must be a Circle W3S wallet UUID or an on-chain 0x address."
    )


def _env(env: Mapping[str, str] | None) -> Mapping[str, str]:
    return os.environ if env is None else env


def _api_key(env: Mapping[str, str]) -> str:
    key = env.get("CIRCLE_API_KEY", "").strip()
    if not key:
        raise CircleWalletError("CIRCLE_API_KEY is not set.")
    return key


def _wallet_id(env: Mapping[str, str]) -> str:
    wallet_id = env.get("CIRCLE_WALLET_ID", "").strip()
    if not wallet_id:
        raise CircleWalletError("CIRCLE_WALLET_ID is not set.")
    return wallet_id


def _blockchain(env: Mapping[str, str]) -> str:
    return env.get("CIRCLE_BLOCKCHAIN", "BASE-SEPOLIA").strip() or "BASE-SEPOLIA"


def _rpc_url(env: Mapping[str, str]) -> str:
    return env.get("BASE_SEPOLIA_RPC_URL", "").strip()


def _is_wallet_uuid(value: str) -> bool:
    return bool(UUID_RE.match(value))


def _is_eth_address(value: str) -> bool:
    return value.startswith("0x") and len(value) == 42


def _auth_headers(env: Mapping[str, str]) -> dict[str, str]:
    return {"Authorization": f"Bearer {_api_key(env)}"}


def _circle_subprocess_env(env: Mapping[str, str]) -> dict[str, str]:
    merged = dict(os.environ)
    merged.setdefault("CIRCLE_ACCEPT_TERMS", "1")
    api_key = env.get("CIRCLE_API_KEY", "").strip()
    if api_key:
        merged.setdefault("CIRCLE_API_KEY", api_key)
    return merged


def _run_circle_cli(
    command: list[str],
    *,
    env: Mapping[str, str],
    timeout: float = 60,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
        env=_circle_subprocess_env(env),
    )


def _sum_usdc_total(balances: list[WalletTokenBalance], test_usdc_address: str) -> float:
    total = 0.0
    matched = False
    test_addr = test_usdc_address.lower()
    for item in balances:
        symbol = (item.symbol or "").upper()
        token_addr = (item.token_address or "").lower()
        is_usdc = symbol == "USDC" or (token_addr and token_addr == test_addr)
        if not is_usdc:
            continue
        matched = True
        try:
            total += float(item.amount)
        except ValueError:
            continue
    if not matched and balances:
        try:
            total += float(balances[0].amount)
        except ValueError:
            pass
    return round(total, 6)


def _parse_balance_payload(payload: dict[str, Any], blockchain: str) -> list[WalletTokenBalance]:
    token_balances = payload.get("data", {}).get("tokenBalances", payload.get("tokenBalances", []))
    if not isinstance(token_balances, list):
        return []
    parsed: list[WalletTokenBalance] = []
    for entry in token_balances:
        if not isinstance(entry, dict):
            continue
        token = entry.get("token", entry)
        if not isinstance(token, dict):
            token = {}
        amount = str(entry.get("amount", token.get("amount", "0")))
        symbol = str(token.get("symbol", entry.get("symbol", "USDC")))
        chain = str(token.get("blockchain", entry.get("blockchain", blockchain)))
        token_address = str(token.get("tokenAddress", entry.get("tokenAddress", "")))
        parsed.append(
            WalletTokenBalance(
                symbol=symbol,
                amount=amount,
                blockchain=chain,
                token_address=token_address,
            )
        )
    return parsed


def _parse_transactions_payload(payload: dict[str, Any]) -> list[WalletTransactionItem]:
    transactions = payload.get("data", {}).get("transactions", payload.get("transactions", []))
    if not isinstance(transactions, list):
        return []
    parsed: list[WalletTransactionItem] = []
    for entry in transactions:
        if not isinstance(entry, dict):
            continue
        amounts = entry.get("amounts", [])
        amount = "0"
        if isinstance(amounts, list) and amounts:
            amount = str(amounts[0])
        tx_hash = str(entry.get("txHash", entry.get("transactionHash", "")))
        parsed.append(
            WalletTransactionItem(
                id=str(entry.get("id", tx_hash or uuid.uuid4().hex[:12])),
                state=str(entry.get("state", "")),
                tx_hash=tx_hash,
                amount_usdc=float(amount) if amount else 0.0,
                operation=str(entry.get("operation", "")),
                transaction_type=str(entry.get("transactionType", entry.get("type", ""))),
                create_date=str(entry.get("createDate", entry.get("createdAt", ""))),
                explorer_url=blockscout_tx_url(tx_hash) if tx_hash.startswith("0x") else "",
            )
        )
    return parsed


def _parse_circle_cli_transactions(payload: Any) -> list[WalletTransactionItem]:
    if isinstance(payload, list):
        entries = payload
    elif isinstance(payload, dict):
        data = payload.get("data", payload)
        if isinstance(data, dict):
            entries = data.get("transactions", data.get("items", []))
        else:
            entries = data if isinstance(data, list) else []
    else:
        entries = []
    if not isinstance(entries, list):
        return []

    parsed: list[WalletTransactionItem] = []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        amounts = entry.get("amounts", entry.get("amount", []))
        amount = "0"
        if isinstance(amounts, list) and amounts:
            amount = str(amounts[0])
        elif isinstance(amounts, (int, float, str)):
            amount = str(amounts)
        tx_hash = str(
            entry.get("txHash")
            or entry.get("transactionHash")
            or entry.get("hash")
            or entry.get("transaction")
            or ""
        )
        parsed.append(
            WalletTransactionItem(
                id=str(entry.get("id", tx_hash or uuid.uuid4().hex[:12])),
                state=str(entry.get("state", entry.get("status", ""))),
                tx_hash=tx_hash,
                amount_usdc=float(amount) if amount else 0.0,
                operation=str(entry.get("operation", "")),
                transaction_type=str(entry.get("transactionType", entry.get("txType", entry.get("type", "")))),
                create_date=str(entry.get("createDate", entry.get("createdAt", entry.get("timestamp", "")))),
                explorer_url=blockscout_tx_url(tx_hash) if tx_hash.startswith("0x") else "",
            )
        )
    return parsed


def _fetch_agent_transactions_via_cli(
    env: Mapping[str, str],
    wallet_address: str,
    limit: int,
) -> WalletTransactionsResponse:
    blockchain = _blockchain(env)
    command = _circle_cli_command(
        "transaction",
        "list",
        "--address",
        wallet_address,
        "--chain",
        blockchain,
        "--limit",
        str(max(1, min(limit, 50))),
        "--output",
        "json",
    )
    try:
        completed = _run_circle_cli(command, env=env, timeout=60)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise CircleWalletError(f"Circle CLI transaction list failed: {exc}") from exc

    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout or "unknown error").strip()
        raise CircleWalletError(f"Circle CLI transaction list failed ({completed.returncode}): {detail}")

    stdout = (completed.stdout or "").strip()
    if not stdout:
        return WalletTransactionsResponse(
            wallet_id=wallet_address,
            transactions=[],
            simulated=False,
            provenance=CLI_PROVENANCE,
        )

    try:
        payload = json.loads(stdout)
    except json.JSONDecodeError as exc:
        raise CircleWalletError(f"Circle CLI returned non-JSON output: {stdout[:200]}") from exc

    transactions = _parse_circle_cli_transactions(payload)
    return WalletTransactionsResponse(
        wallet_id=wallet_address,
        transactions=transactions[:limit],
        simulated=False,
        provenance=CLI_PROVENANCE,
    )


def _mock_balance_response(env: Mapping[str, str]) -> WalletBalanceResponse:
    wallet_id = env.get("CIRCLE_WALLET_ID", "mock-wallet").strip() or "mock-wallet"
    blockchain = _blockchain(env)
    response = WalletBalanceResponse(
        wallet_id=wallet_id,
        usdc_total=MOCK_WALLET_USDC,
        balances=[
            WalletTokenBalance(
                symbol="USDC",
                amount=str(MOCK_WALLET_USDC),
                blockchain=blockchain,
                token_address=resolve_base_sepolia_usdc_address(env),
            )
        ],
        simulated=True,
        provenance=MOCK_PROVENANCE,
    )
    return _attach_broker_payer(env, response)


def _mock_transactions_response(env: Mapping[str, str]) -> WalletTransactionsResponse:
    wallet_id = env.get("CIRCLE_WALLET_ID", "mock-wallet").strip() or "mock-wallet"
    tx_hash = "0x23f359f2ba32e8a3cf55fbbc959e3692733a728fe3ebf6b05d22d3c1e84007e5"
    return WalletTransactionsResponse(
        wallet_id=wallet_id,
        transactions=[
            WalletTransactionItem(
                id="mock-circle-tx-1",
                state="complete",
                tx_hash=tx_hash,
                amount_usdc=0.01,
                operation="TRANSFER",
                transaction_type="OUTBOUND",
                create_date="2026-06-20T12:00:00Z",
                explorer_url=blockscout_tx_url(tx_hash),
            )
        ],
        simulated=True,
        provenance=MOCK_PROVENANCE,
    )


def _env_address(env: Mapping[str, str], key: str) -> str:
    raw = env.get(key, "").strip()
    if not raw:
        return ""
    return raw.split("#", 1)[0].strip()


def _read_onchain_usdc_balance(env: Mapping[str, str], wallet_address: str) -> float:
    response = _fetch_onchain_balances(env, wallet_address)
    return response.usdc_total


def _attach_broker_payer(env: Mapping[str, str], response: WalletBalanceResponse) -> WalletBalanceResponse:
    deployer = _env_address(env, "BASE_SEPOLIA_DEPLOYER_ADDRESS")
    if not deployer.startswith("0x"):
        return response
    deployer = Web3.to_checksum_address(deployer)
    if preflight_session_mode(env) == SessionMode.LIVE:
        try:
            payer_usdc = _read_onchain_usdc_balance(env, deployer)
        except Exception:
            payer_usdc = None
    else:
        payer_usdc = MOCK_WALLET_USDC
    return response.model_copy(
        update={
            "broker_payer_address": deployer,
            "broker_payer_usdc": payer_usdc,
        }
    )


def _fetch_w3s_balances(env: Mapping[str, str], wallet_id: str) -> WalletBalanceResponse:
    blockchain = _blockchain(env)
    usdc = resolve_base_sepolia_usdc_address(env)
    params = {"tokenAddress": usdc}
    url = f"{CIRCLE_API_BASE}/v1/w3s/wallets/{wallet_id}/balances"
    try:
        with httpx.Client(timeout=30.0) as client:
            response = client.get(url, headers=_auth_headers(env), params=params)
            response.raise_for_status()
            payload = response.json()
    except httpx.HTTPStatusError as exc:
        detail = exc.response.text.strip() or str(exc)
        raise CircleWalletError(f"Circle balance request failed ({exc.response.status_code}): {detail}") from exc
    except httpx.HTTPError as exc:
        raise CircleWalletError(f"Circle balance request failed: {exc}") from exc

    balances = _parse_balance_payload(payload, blockchain)
    return WalletBalanceResponse(
        wallet_id=wallet_id,
        usdc_total=_sum_usdc_total(balances, usdc),
        balances=balances,
        simulated=False,
        provenance=W3S_PROVENANCE,
    )


def _fetch_onchain_balances(env: Mapping[str, str], wallet_address: str) -> WalletBalanceResponse:
    rpc_url = _rpc_url(env)
    if not rpc_url:
        raise CircleWalletError("BASE_SEPOLIA_RPC_URL is not set.")
    usdc = resolve_base_sepolia_usdc_address(env)
    blockchain = _blockchain(env)
    w3 = Web3(Web3.HTTPProvider(rpc_url))
    if not w3.is_connected():
        raise CircleWalletError("Base Sepolia RPC is not reachable.")
    contract = w3.eth.contract(
        address=Web3.to_checksum_address(usdc),
        abi=ERC20_BALANCE_OF_ABI,
    )
    raw_balance = contract.functions.balanceOf(Web3.to_checksum_address(wallet_address)).call()
    amount_str = str(raw_balance / 10**USDC_DECIMALS).rstrip("0").rstrip(".") or "0"
    balances = [
        WalletTokenBalance(
            symbol="USDC",
            amount=amount_str,
            blockchain=blockchain,
            token_address=usdc,
        )
    ]
    return WalletBalanceResponse(
        wallet_id=wallet_address,
        usdc_total=round(float(amount_str), 6),
        balances=balances,
        simulated=False,
        provenance=ONCHAIN_PROVENANCE,
    )


def _fetch_live_balances(env: Mapping[str, str]) -> WalletBalanceResponse:
    wallet_id = _wallet_id(env)
    if _is_wallet_uuid(wallet_id):
        return _fetch_w3s_balances(env, wallet_id)
    if _is_eth_address(wallet_id):
        return _fetch_onchain_balances(env, wallet_id)
    raise CircleWalletError(
        "CIRCLE_WALLET_ID must be a Circle W3S wallet UUID or an on-chain 0x address."
    )


def _fetch_live_transactions(env: Mapping[str, str], limit: int) -> WalletTransactionsResponse:
    wallet_id = _wallet_id(env)
    if _is_eth_address(wallet_id):
        return _fetch_agent_transactions_via_cli(env, wallet_id, limit)

    blockchain = _blockchain(env)
    page_size = max(1, min(limit, 50))
    params = {
        "walletIds": wallet_id,
        "pageSize": str(page_size),
        "order": "DESC",
    }
    url = f"{CIRCLE_API_BASE}/v1/w3s/transactions"
    try:
        with httpx.Client(timeout=30.0) as client:
            response = client.get(url, headers=_auth_headers(env), params=params)
            response.raise_for_status()
            payload = response.json()
    except httpx.HTTPStatusError as exc:
        detail = exc.response.text.strip() or str(exc)
        raise CircleWalletError(
            f"Circle transactions request failed ({exc.response.status_code}): {detail}"
        ) from exc
    except httpx.HTTPError as exc:
        raise CircleWalletError(f"Circle transactions request failed: {exc}") from exc

    transactions = _parse_transactions_payload(payload)
    return WalletTransactionsResponse(
        wallet_id=wallet_id,
        transactions=transactions[:limit],
        simulated=False,
        provenance=W3S_PROVENANCE,
    )


def fetch_wallet_balance(env: Mapping[str, str] | None = None) -> WalletBalanceResponse:
    current = _env(env)
    if preflight_session_mode(current) != SessionMode.LIVE:
        return _mock_balance_response(current)
    return _attach_broker_payer(current, _fetch_live_balances(current))


def fetch_wallet_transactions(
    limit: int = 25,
    env: Mapping[str, str] | None = None,
) -> WalletTransactionsResponse:
    current = _env(env)
    if preflight_session_mode(current) != SessionMode.LIVE:
        return _mock_transactions_response(current)
    return _fetch_live_transactions(current, limit)


def _circle_cli_command(*parts: str) -> list[str]:
    """Resolve Circle CLI — prefer global ``circle``, else ``npx @circle-fin/cli``."""
    if shutil.which("circle"):
        return ["circle", *parts]
    return ["npx", "--yes", "@circle-fin/cli", *parts]


def _lookup_agent_wallet_address_from_cli(env: Mapping[str, str]) -> str:
    blockchain = _blockchain(env).replace("-SEPOLIA", "").upper()
    if blockchain == "BASE":
        chain_flag = "BASE"
    else:
        chain_flag = blockchain
    try:
        completed = _run_circle_cli(
            _circle_cli_command("wallet", "list", "--type", "agent", "--chain", chain_flag),
            env=env,
            timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired):
        return ""
    output = (completed.stdout or "") + (completed.stderr or "")
    match = re.search(r"0x[a-fA-F0-9]{40}", output)
    return match.group(0) if match else ""


def _extract_tx_hash(payload: Any) -> str:
    if isinstance(payload, dict):
        for key in ("txHash", "transaction", "transactionHash", "tx_hash", "hash"):
            value = payload.get(key)
            if isinstance(value, str) and value.startswith("0x"):
                return value
        for value in payload.values():
            found = _extract_tx_hash(value)
            if found:
                return found
    elif isinstance(payload, list):
        for item in payload:
            found = _extract_tx_hash(item)
            if found:
                return found
    return ""


def _parse_circle_cli_output(stdout: str, stderr: str) -> dict[str, Any]:
    for chunk in (stdout, stderr):
        chunk = chunk.strip()
        if not chunk:
            continue
        try:
            parsed = json.loads(chunk)
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            pass
        match = re.search(r"0x[a-fA-F0-9]{64}", chunk)
        if match:
            return {"txHash": match.group(0)}
    return {}


def transfer_premium_usdc(
    *,
    amount_usdc: float,
    destination_address: str,
    idempotency_key: str,
    reference: str,
    env: Mapping[str, str] | None = None,
) -> TransferReceipt:
    current = _env(env)
    if amount_usdc <= 0:
        raise CircleWalletError("Premium must be greater than zero.")

    if preflight_session_mode(current) != SessionMode.LIVE:
        return TransferReceipt(
            reference=reference,
            amount_usdc=amount_usdc,
            destination_address=destination_address,
            tx_hash=f"mock-transfer:{idempotency_key}",
            simulated=True,
            provenance=MOCK_PROVENANCE,
            attempted=True,
        )

    blockchain = _blockchain(current)
    command = _circle_cli_command(
        "wallet",
        "transfer",
        destination_address,
        "--amount",
        f"{amount_usdc:.6f}".rstrip("0").rstrip("."),
        "--chain",
        blockchain,
    )
    wallet_id = current.get("CIRCLE_WALLET_ID", "").strip()
    if _is_eth_address(wallet_id):
        command.extend(["--address", wallet_id])

    try:
        completed = _run_circle_cli(command, env=current, timeout=120)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return TransferReceipt(
            reference=reference,
            amount_usdc=amount_usdc,
            destination_address=destination_address,
            attempted=True,
            provenance=TRANSFER_PROVENANCE,
            error=f"Circle transfer command failed: {exc}",
        )

    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout or "unknown error").strip()
        return TransferReceipt(
            reference=reference,
            amount_usdc=amount_usdc,
            destination_address=destination_address,
            attempted=True,
            provenance=TRANSFER_PROVENANCE,
            error=f"Circle transfer failed ({completed.returncode}): {detail}",
        )

    parsed = _parse_circle_cli_output(completed.stdout, completed.stderr)
    tx_hash = _extract_tx_hash(parsed)
    if not tx_hash:
        return TransferReceipt(
            reference=reference,
            amount_usdc=amount_usdc,
            destination_address=destination_address,
            attempted=True,
            provenance=TRANSFER_PROVENANCE,
            error="Circle transfer succeeded but no transaction hash was found in CLI output.",
        )

    return TransferReceipt(
        reference=reference,
        amount_usdc=amount_usdc,
        destination_address=destination_address,
        tx_hash=tx_hash,
        simulated=False,
        provenance=TRANSFER_PROVENANCE,
        attempted=True,
    )


def ensure_broker_payer_usdc(
    *,
    required_usdc: float,
    env: Mapping[str, str] | None = None,
) -> TransferReceipt | None:
    """Ensure the on-chain broker payer holds enough test USDC before ``transferFrom``.

    Live ``InsuranceManager.purchasePolicy`` pulls premium USDC from
    ``BASE_SEPOLIA_DEPLOYER_ADDRESS`` (not the Circle agent wallet). When that
    deployer is short, pull the gap from the Circle agent wallet first.
    ERC-20 ``approve`` for the contract is handled separately by the Web3 client.
    """
    current = _env(env)
    if preflight_session_mode(current) != SessionMode.LIVE:
        return None
    if required_usdc <= 0:
        return None

    deployer = _env_address(current, "BASE_SEPOLIA_DEPLOYER_ADDRESS")
    if not deployer.startswith("0x"):
        return None

    deployer = Web3.to_checksum_address(deployer)
    current_balance = _read_onchain_usdc_balance(current, deployer)
    shortfall = round(required_usdc - current_balance, 6)
    if shortfall <= 0:
        return None

    receipt = transfer_premium_usdc(
        amount_usdc=shortfall,
        destination_address=deployer,
        idempotency_key=f"fund-deployer:{uuid.uuid4().hex[:12]}",
        reference=f"fund-broker-payer:{shortfall}",
        env=current,
    )
    if receipt.error:
        raise CircleWalletError(
            f"Broker payer {deployer} needs {required_usdc:.6f} USDC for the on-chain premium "
            f"(currently {current_balance:.6f} USDC). Circle top-up failed: {receipt.error}"
        )

    for _ in range(30):
        if _read_onchain_usdc_balance(current, deployer) + 1e-6 >= required_usdc:
            return receipt
        time.sleep(2)

    raise CircleWalletError(
        f"Broker payer {deployer} still below {required_usdc:.6f} USDC after Circle top-up "
        f"(tx {receipt.tx_hash or 'unknown'})."
    )


def mock_transfer_receipt(*, reference: str, amount_usdc: float, destination_address: str) -> TransferReceipt:
    return TransferReceipt(
        reference=reference,
        amount_usdc=amount_usdc,
        destination_address=destination_address,
        tx_hash=f"mock-transfer:{uuid.uuid4().hex[:12]}",
        simulated=True,
        provenance=MOCK_PROVENANCE,
        attempted=True,
    )
