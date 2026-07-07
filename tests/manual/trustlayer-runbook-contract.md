# TrustLayer runbook contract snapshot

This snapshot captures the minimum runbook strings the repo contract test
depends on. Keep it aligned with the active `/opt/infra/docs/trustlayer.md`
runbook when the deployment shape changes.

- one public user-facing origin: `https://trustlayer.37-27-94-136.sslip.io`
- one internal API base on the Compose network: `http://trustlayer-api:8000`
- The former `trustlayer-api.37-27-94-136.sslip.io` hostname is no longer part
  of the TrustLayer public surface and returns 404 at the edge
- `TRUSTLAYER_API_TOKEN`
- The Streamlit and FastAPI containers must share the same `TRUSTLAYER_API_TOKEN`
  value
- The browser voice path no longer has a local browser-speech fallback
- If ElevenLabs is not configured, `/api/betty/tts` returns `503`
