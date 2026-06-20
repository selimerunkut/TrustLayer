# CoverPilot repo notes

This file is the durable scratchpad for repo-specific operating facts. Keep it
short, current, and biased toward things future agents are likely to forget.

## Stack

- Frontend: Streamlit in `app/`
- Backend: FastAPI in `backend/`
- Contracts: Foundry / Solidity in `contracts/`
- Python version + environment: `uv`
- Python dependencies: `pyproject.toml` + `uv.lock`

## Python workflow

- Use `uv` for interpreter management and dependency sync.
- Do not introduce `pip`, Poetry, or ad hoc virtualenv workflows unless the
  project direction changes.
- Common commands:
  - `uv sync`
  - `uv run pytest`
  - `uv run uvicorn backend.main:app --reload`
  - `uv run streamlit run app/streamlit_app.py`

## Circle setup

- This repo is wired for the **Circle Agent Wallet / x402** path.
- `CIRCLE_API_KEY` comes from the Circle Console.
- `CIRCLE_WALLET_ID` comes from the Circle wallet / agent-wallet flow.
- Circle CLI is installed as `@circle-fin/cli`.
- Useful commands:
  - `circle wallet login you@example.com`
  - `circle wallet list --type agent --chain BASE`
  - `circle wallet create --type agent`

## Live-demo gates

- `CIRCLE_READY=true` and `BASE_SEPOLIA_READY=true` are the live-mode gates.
- The project also expects:
  - `BASE_SEPOLIA_RPC_URL`
  - `BASE_SEPOLIA_CONTRACT_ADDRESS`
  - `BASE_SEPOLIA_TEST_USDC_ADDRESS`
  - `ORACLE_PRIVILEGED_TOKEN`
- Keep real secrets in local `.env`; do not commit them.

## Repo conventions learned so far

- `README.md` describes the intended demo stack as:
  - Streamlit frontend
  - FastAPI backend
  - LangChain broker
  - Pydantic schemas
  - Circle Agent Wallet / x402 integration
  - Base Sepolia / test-USDC contract flow
- The repo currently treats `CIRCLE_API_KEY` + `CIRCLE_WALLET_ID` as the
  minimal live Circle readiness pair.
- Favor small, reversible edits and keep verification close to the change.

