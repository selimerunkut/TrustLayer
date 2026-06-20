# CoverPilot MVP

This repository is being scaffolded to match the approved ultragoal plan:

- Streamlit frontend
- FastAPI backend
- LangChain broker
- Pydantic schemas
- Circle Agent Wallet / x402 integration
- Base Sepolia / test-USDC contract flow
- Solidity contract layer

The implementation is intentionally phased. The first verified slice is the fixed-stack scaffold.

## Environment

Copy `.env.example` to `.env` when you want a local override file for the
demo session-mode gates and future live integration values. The code treats the
checked-in example as documentation; real credentials belong in your local
environment.

## Toolchain

- Use `uv` to manage the Python interpreter version and environment.
- Keep dependency declarations in `pyproject.toml`.

Common commands:

```bash
uv sync
uv run pytest
uv run streamlit run app/streamlit_app.py
uv run uvicorn backend.main:app --reload
```

## Circle / x402 live-testnet notes

- `CIRCLE_API_KEY` comes from the Circle Console.
- `CIRCLE_WALLET_ID` is the Circle agent-wallet identifier string, not the onchain address.
- `circle wallet login` uses email OTP for the agent-wallet session.
- Before `circle services pay` can sign x402 payments, the agent wallet must be deployed on-chain at least once. In this repo, a zero-value self-transfer on Base Sepolia was enough to deploy it.
- The Base Sepolia test wallet can be funded with the Circle faucet.
- A working Base Sepolia x402 echo target for verification is:
  - `https://x402.payai.network/api/base-sepolia/paid-content`
- The live x402 Echo merchant returns a paid response and refunds the test payment, which makes it useful for proving the payment flow without burning funds.
- The live evidence bundle for this repo is stored in `tests/manual/evidence-bundle.json` and `tests/manual/live-demo-transcript.md`.
