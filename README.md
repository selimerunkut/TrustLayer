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
uv sync --extra dev
uv run python -m pytest
uv run streamlit run app/streamlit_app.py
uv run uvicorn backend.main:app --reload
```

Streamlit hosts **Betty** (TrustLayer broker): set `OPENAI_API_KEY` in `.env` (see `.env.example`). The same `coverpilot_conversation` tools and prompts power the chat; the mock broker uses the same research-fee bands as `backend.services.receipts`.
