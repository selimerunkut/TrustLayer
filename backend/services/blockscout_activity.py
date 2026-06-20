"""On-chain wallet activity from Base Sepolia Blockscout (token transfers + deployer txs)."""

from __future__ import annotations

import logging
import os
from collections.abc import Mapping
from typing import Any

import httpx

from backend.schemas import WalletTransactionItem
from backend.services.base_sepolia import blockscout_tx_url

logger = logging.getLogger(__name__)

BLOCKSCOUT_API = "https://base-sepolia.blockscout.com/api/v2"
BLOCKSCOUT_PROVENANCE = "base:sepolia:blockscout"


def _env(env: Mapping[str, str] | None = None) -> dict[str, str]:
    return dict(os.environ) if env is None else dict(env)


def _env_address(env: Mapping[str, str], key: str) -> str:
    raw = env.get(key, "").strip()
    if not raw:
        return ""
    return raw.split("#", 1)[0].strip()


def _amount_usdc(total: dict[str, Any] | None) -> float:
    if not isinstance(total, dict):
        return 0.0
    raw = total.get("value")
    decimals = int(total.get("decimals") or 6)
    try:
        return round(int(raw) / 10**decimals, 6)
    except (TypeError, ValueError):
        return 0.0


def _address_hash(entry: dict[str, Any] | None) -> str:
    if not isinstance(entry, dict):
        return ""
    return str(entry.get("hash") or "")


def _parse_token_transfer(entry: dict[str, Any], *, wallet_address: str) -> WalletTransactionItem | None:
    tx_hash = str(entry.get("transaction_hash") or "")
    if not tx_hash.startswith("0x"):
        return None
    wallet_l = wallet_address.lower()
    from_addr = _address_hash(entry.get("from")).lower()
    to_addr = _address_hash(entry.get("to")).lower()
    amount = _amount_usdc(entry.get("total"))
    if to_addr == wallet_l:
        operation = "USDC in"
    elif from_addr == wallet_l:
        operation = "USDC out"
    else:
        operation = "USDC transfer"
    ts = str(entry.get("timestamp") or "")
    log_index = entry.get("log_index", 0)
    return WalletTransactionItem(
        id=f"{tx_hash}:{log_index}",
        state="confirmed",
        tx_hash=tx_hash,
        amount_usdc=amount,
        operation=operation,
        transaction_type="token_transfer",
        create_date=ts.replace("T", " ").replace(".000000Z", " UTC") if ts else "",
        explorer_url=blockscout_tx_url(tx_hash),
    )


def _parse_address_transaction(entry: dict[str, Any]) -> WalletTransactionItem | None:
    tx_hash = str(entry.get("hash") or "")
    if not tx_hash.startswith("0x"):
        return None
    method = str(entry.get("method") or "")
    if not method and entry.get("transaction_types"):
        types = entry.get("transaction_types") or []
        method = str(types[0]) if types else "transaction"
    amount = 0.0
    token_transfers = entry.get("token_transfers") or []
    if isinstance(token_transfers, list) and token_transfers:
        amount = _amount_usdc(token_transfers[0].get("total"))
    ts = str(entry.get("timestamp") or "")
    state = "confirmed" if entry.get("status") == "ok" else str(entry.get("status") or "unknown")
    return WalletTransactionItem(
        id=tx_hash,
        state=state,
        tx_hash=tx_hash,
        amount_usdc=amount,
        operation=method or "transaction",
        transaction_type=str(entry.get("type") or "contract_call"),
        create_date=ts.replace("T", " ").replace(".000000Z", " UTC") if ts else "",
        explorer_url=blockscout_tx_url(tx_hash),
    )


def _get_json(path: str, *, timeout: float = 20.0) -> dict[str, Any]:
    url = f"{BLOCKSCOUT_API}{path}"
    with httpx.Client(timeout=timeout) as client:
        response = client.get(url)
        response.raise_for_status()
        payload = response.json()
    return payload if isinstance(payload, dict) else {}


def fetch_blockscout_token_transfers(address: str, *, limit: int = 15) -> list[WalletTransactionItem]:
    if not address.startswith("0x"):
        return []
    try:
        payload = _get_json(f"/addresses/{address}/token-transfers")
    except Exception:
        logger.debug("Blockscout token transfers failed for %s", address, exc_info=True)
        return []
    items = payload.get("items") or []
    parsed: list[WalletTransactionItem] = []
    for entry in items[:limit]:
        if not isinstance(entry, dict):
            continue
        item = _parse_token_transfer(entry, wallet_address=address)
        if item:
            parsed.append(item)
    return parsed


def fetch_blockscout_address_transactions(address: str, *, limit: int = 15) -> list[WalletTransactionItem]:
    if not address.startswith("0x"):
        return []
    try:
        payload = _get_json(f"/addresses/{address}/transactions")
    except Exception:
        logger.debug("Blockscout transactions failed for %s", address, exc_info=True)
        return []
    items = payload.get("items") or []
    parsed: list[WalletTransactionItem] = []
    for entry in items[:limit]:
        if not isinstance(entry, dict):
            continue
        item = _parse_address_transaction(entry)
        if item:
            parsed.append(item)
    return parsed


def merge_wallet_transactions(
    *groups: list[WalletTransactionItem],
    limit: int,
) -> list[WalletTransactionItem]:
    seen: set[str] = set()
    unique: list[WalletTransactionItem] = []
    for group in groups:
        for item in group:
            key = item.id or item.tx_hash
            if not key or key in seen:
                continue
            seen.add(key)
            unique.append(item)
    unique.sort(key=lambda tx: tx.create_date or "", reverse=True)
    return unique[:limit]


def fetch_onchain_wallet_activity(
    *,
    limit: int = 15,
    env: Mapping[str, str] | None = None,
) -> list[WalletTransactionItem]:
    """Circle wallet token transfers plus deployer contract calls (e.g. purchasePolicy)."""
    current = _env(env)
    wallet = _env_address(current, "CIRCLE_WALLET_ID")
    deployer = _env_address(current, "BASE_SEPOLIA_DEPLOYER_ADDRESS")
    wallet_txs = fetch_blockscout_token_transfers(wallet, limit=limit) if wallet.startswith("0x") else []
    deployer_txs = fetch_blockscout_address_transactions(deployer, limit=limit) if deployer.startswith("0x") else []
    return merge_wallet_transactions(wallet_txs, deployer_txs, limit=limit)
