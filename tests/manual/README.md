# Manual live testnet evidence bundle

Use this directory to record the final live-path evidence required by the CoverPilot ultragoal.

The live acceptance bundle should include:

- commit hash
- test summary
- screenshots
- logs
- policy IDs
- idempotency keys
- receipt references
- transaction hashes
- Base Sepolia contract address
- live policy creation receipt
- live payout receipt
- fallback mode flag
- short demo transcript

## Required live checklist

- [ ] Disclaimer visible before authorization
- [ ] Session mode is `LIVE`
- [ ] Circle Agent Wallet identity is loaded
- [ ] x402 paid request succeeds
- [ ] Base Sepolia contract is reachable
- [ ] Policy is created onchain
- [ ] Privileged oracle resolution is submitted
- [ ] Automatic payout or expiry outcome is recorded
- [ ] Repeat submission does not create a duplicate side effect
- [ ] Evidence bundle is saved in this directory

## Recommended bundle files

- `evidence-bundle.json`
- `screenshots/`
- `logs/`
- `tx-hashes.txt`
- `demo-transcript.md`

Do not record simulated results in a way that can be confused with real settlement.
