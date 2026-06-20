from dataclasses import dataclass

from backend.schemas import OracleResolution, PolicyRecord


@dataclass(frozen=True)
class ChainWriteResult:
    policy_id: str
    tx_hash: str
    simulated: bool = False
    provenance: str = ""


def _record_chain_write(
    policy_id: str,
    *,
    tx_hash: str,
    simulated: bool = False,
    provenance: str = "base:sepolia",
) -> ChainWriteResult:
    return ChainWriteResult(
        policy_id=policy_id,
        tx_hash=tx_hash,
        simulated=simulated,
        provenance=provenance,
    )


def record_policy_purchase(
    policy: PolicyRecord,
    *,
    tx_hash: str,
    simulated: bool = False,
    provenance: str = "base:sepolia",
) -> ChainWriteResult:
    return _record_chain_write(policy.policy_id, tx_hash=tx_hash, simulated=simulated, provenance=provenance)


def record_policy_rejection(
    policy: PolicyRecord,
    *,
    tx_hash: str,
    simulated: bool = False,
    provenance: str = "base:sepolia",
) -> ChainWriteResult:
    return _record_chain_write(policy.policy_id, tx_hash=tx_hash, simulated=simulated, provenance=provenance)


def record_oracle_resolution(
    resolution: OracleResolution,
    *,
    tx_hash: str,
    simulated: bool = False,
    provenance: str = "base:sepolia",
) -> ChainWriteResult:
    return _record_chain_write(resolution.policy_id, tx_hash=tx_hash, simulated=simulated, provenance=provenance)
