# TrustLayer repo notes

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
- `CIRCLE_WALLET_ID` is the Circle wallet identifier string from the agent-wallet flow
  (for example `VDW-135052`), not the blockchain address.
- Circle CLI is installed as `@circle-fin/cli`.
- Useful commands:
  - `circle wallet login you@example.com`
  - `circle wallet login se@cypherx.tech --type agent --testnet --init`
  - `circle wallet login --request <request-id> --otp <code>`
  - `circle wallet list --type agent --chain BASE`
  - `circle wallet create --type agent`
- Treat the run-scoped evidence bundle as the authoritative home for live coordinates and receipts.
- `NEBIUS_API_KEY` is another runtime secret; keep it in local `.env`, the
  sample env docs, and Coolify whenever the Nebius integration is active.

## Base Sepolia deployment

- Deploy contracts with the lightweight Python deploy script in `scripts/`
  rather than adding a heavier JS toolchain.
- Use a burner EOA for deployment:
  - generate the address locally
  - fund it with Base Sepolia test ETH
  - keep the private key only in local `.env`
- Keep the live-testnet proof set in the run evidence bundle and transcript rather than in this scratchpad.
- Current funded burner deployer:
  - `0xBA3330FB593dEb0203a5801B2E2f6f295f76FAd8`
- `BASE_SEPOLIA_TEST_USDC_ADDRESS`:
  - `0x036CbD53842c5426634e7929541eC2318f3dCF7e`
- Current live contract / `BASE_SEPOLIA_CONTRACT_ADDRESS`:
  - `0xC157bA30863611F2eCB21BAEf556884a72ec559B`

## Live-demo gates

- `CIRCLE_READY=true` and `BASE_SEPOLIA_READY=true` are the live-mode gates.
- The project also expects:
  - `BASE_SEPOLIA_RPC_URL`
  - `BASE_SEPOLIA_CONTRACT_ADDRESS`
  - `BASE_SEPOLIA_TEST_USDC_ADDRESS`
  - `BASE_SEPOLIA_DEPLOYER_ADDRESS`
  - `BASE_SEPOLIA_DEPLOYER_PRIVATE_KEY`
  - `ORACLE_PRIVILEGED_TOKEN`
- Keep real secrets in local `.env`; do not commit them.

## Coolify deployment

- Local Coolify dashboard: `http://37.27.94.136:8000`
- Local infra docs live in `/opt/infra`
- For local Coolify deployments, use an `sslip.io` hostname for public reachability
  (for example `trustlayer.37-27-94-136.sslip.io`).
- Coolify deploy-only API token for TrustLayer automation lives in
  `/opt/infra/.env` as `COOLIFY_API_KEY`; do not copy the secret into the repo.
- Prepared Coolify deploy key UUID for the private GitHub repo:
  `xjsn8p86itmml1m92atodu1h`
- The GitHub deploy key is already added to the TrustLayer repo, so Coolify
  should use the deploy-key source path instead of prompting for HTTP auth.
- Coolify may start with `SOURCE_COMMIT=unknown`; do not reintroduce a hard
  build failure on that value.
- GitHub Actions now patches the Coolify app's `SOURCE_COMMIT` env to the
  pushed commit SHA before each deploy; keep the `/version` check wired to that
  commit-synchronization step.
- Add TrustLayer deployment notes under `/opt/infra/docs/` when updating the
  infra playbook.

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
