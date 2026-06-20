# TrustLayer

TrustLayer is the approved demo app formerly referred to as CoverPilot in older
notes. The repository is being shaped around a fixed stack:

- Streamlit frontend
- FastAPI backend
- LangChain broker
- Pydantic schemas
- Circle Agent Wallet / x402 integration
- Base Sepolia / test-USDC contract flow
- Solidity contract layer

## Toolchain

- Use `uv` for Python version and environment management.
- Keep dependency declarations in `pyproject.toml` and `uv.lock`.

Common commands:

```bash
uv sync
uv run pytest
uv run streamlit run app/streamlit_app.py
uv run uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000
```

## Local development

Copy `.env.example` to `.env` for local overrides. The app reads the checked-in
example as documentation; secrets stay in your local environment or in Coolify.

Useful runtime variables:

- `OPENAI_API_KEY`
- `OPENROUTER_API_KEY`
- `NEBIUS_API_KEY`
- `CIRCLE_API_KEY`
- `CIRCLE_WALLET_ID`
- `BASE_SEPOLIA_RPC_URL`
- `BASE_SEPOLIA_CONTRACT_ADDRESS`
- `BASE_SEPOLIA_TEST_USDC_ADDRESS`
- `BASE_SEPOLIA_DEPLOYER_ADDRESS`
- `BASE_SEPOLIA_DEPLOYER_PRIVATE_KEY`
- `ORACLE_PRIVILEGED_TOKEN`
- `BETTY_PUBLIC_API_BASE`
- `BETTY_INTERNAL_API_BASE`
- `TRUSTLAYER_GIT_SHA`
- `TRUSTLAYER_CORS_ORIGINS`

## Coolify deployment

TrustLayer is designed to deploy on the local Coolify instance in `/opt/infra`.
The deployment model is one Docker Compose application/resource with two
containers, defined in `compose.yaml` and built from `Dockerfile`:

- `trustlayer-api` on port `8000`
- `trustlayer-web` on port `8501`

Deployment facts:

- Coolify dashboard: `http://37.27.94.136:8000`
- Local infra docs: `/opt/infra`
- Coolify API token for deploy automation lives in `/opt/infra/.env` as
  `COOLIFY_API_KEY`
- The reachable demo hostnames use `sslip.io`
- The frontend should use the public API base
  `https://trustlayer-api.37-27-94-136.sslip.io`
- The Streamlit server should use an internal API base inside Compose
- GitHub pushes to `main` are intended to trigger
  `.github/workflows/deploy-main.yml`, which calls Coolify's deploy endpoint for
  the TrustLayer resource UUID
- The GitHub deploy key is now in place for the private repo, so Coolify can
  clone `selimerunkut/TrustLayer` without falling back to username/password
  auth.
- Coolify's initial build path may not populate `SOURCE_COMMIT`; the Dockerfile
  now treats that value as informational instead of a hard failure so first
  deploys can complete.
- Keep the live Coolify environment variables aligned with `.env` when adding
  new integrations; `OPENROUTER_API_KEY` now lives in both the local override
  file and the sample env docs, and Nebius should follow the same pattern.

The current Base Sepolia and Circle notes live in `AGENTS.md` so future agents do
not have to rediscover them.

## Circle / x402 live-testnet notes

- `CIRCLE_API_KEY` comes from the Circle Console.
- `CIRCLE_WALLET_ID` is the Circle agent-wallet identifier string, not the
  onchain address.
- `circle wallet login` uses email OTP for the agent-wallet session.
- Before `circle services pay` can sign x402 payments, the agent wallet must be
  deployed on-chain at least once. In this repo, a zero-value self-transfer on
  Base Sepolia was enough to deploy it.
- The Base Sepolia test wallet can be funded with the Circle faucet.
- A working Base Sepolia x402 echo target for verification is:
  `https://x402.payai.network/api/base-sepolia/paid-content`
- The live x402 Echo merchant returns a paid response and refunds the test
  payment, which makes it useful for proving the payment flow without burning
  funds.
- The live evidence bundle for this repo is stored in
  `tests/manual/evidence-bundle.json` and
  `tests/manual/live-demo-transcript.md`.
