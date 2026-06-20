# Live demo transcript

- Loaded the live Circle Agent Wallet identity recorded in `tests/manual/evidence-bundle.json`.
- Deployed the Base Sepolia agent wallet onchain with a zero-value self-transfer before payment signing.
- Verified the Base Sepolia policy contract and live policy state for `coverpilot-live-policy-001`.
- Submitted a live x402 payment through Circle CLI to the Base Sepolia echo merchant.
- The merchant returned a paid response and then refunded the test payment.
- Confirmed the onchain policy reached `PayoutPaid` at the end of the Base Sepolia flow.
