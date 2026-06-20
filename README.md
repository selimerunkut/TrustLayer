# TrustLayer MVP

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
uv sync --extra dev
uv run python -m pytest
uv run streamlit run app/streamlit_app.py
uv run uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000
```

Streamlit hosts **Betty** (TrustLayer broker): set `OPENAI_API_KEY` in `.env` (see `.env.example`). The same broker tools and prompts power the chat; the mock broker uses the same research-fee bands as `backend.services.receipts`.

**Voice:** The **Hold to speak** control is always shown under the chat. It calls FastAPI (`uvicorn backend.main:app` on port **8000** by default). Run the API in a second terminal while using voice. Set `ELEVENLABS_*` for TTS and optionally `BETTY_PUBLIC_API_BASE` if the API is not on `127.0.0.1:8000`. Speech rate: `ELEVENLABS_TTS_SPEED` (default `1.1`, clamped to `0.7`–`1.2` for ElevenLabs validation).

## Local Betty (quick test)

```bash
# Terminal 1 — API (voice + health)
uv sync --extra dev
uv run uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000

# Terminal 2 — Streamlit UI
uv run streamlit run app/streamlit_app.py

# One-shot: unit tests (most tests need no API keys)
uv run pytest tests/ -q
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
