from dataclasses import dataclass


@dataclass(frozen=True)
class PaymentEvidence:
    reference: str
    amount_usdc: float
    simulated: bool = False
    provenance: str = ""


@dataclass(frozen=True)
class PaymentReceipt:
    reference: str
    amount_usdc: float
    simulated: bool = False
    provenance: str = ""


def adapt_circle_x402_payment(*, reference: str, amount_usdc: float, simulated: bool = False, provenance: str = "circle:x402") -> PaymentEvidence:
    return PaymentEvidence(
        reference=reference,
        amount_usdc=amount_usdc,
        simulated=simulated,
        provenance=provenance,
    )


def capture_payment_receipt(evidence: PaymentEvidence) -> PaymentReceipt:
    return PaymentReceipt(
        reference=evidence.reference,
        amount_usdc=evidence.amount_usdc,
        simulated=evidence.simulated,
        provenance=evidence.provenance,
    )
