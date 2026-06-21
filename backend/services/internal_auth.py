from __future__ import annotations

import hmac
import os

from fastapi import Header, HTTPException


def _trustlayer_api_token() -> str:
    return os.environ.get("TRUSTLAYER_API_TOKEN", "").strip()


def require_trustlayer_token(x_trustlayer_token: str | None = Header(default=None, alias="X-TrustLayer-Token")) -> None:
    expected_token = _trustlayer_api_token()
    if not expected_token:
        raise HTTPException(status_code=503, detail="service unavailable")
    if not x_trustlayer_token or not hmac.compare_digest(x_trustlayer_token.strip(), expected_token):
        raise HTTPException(status_code=401, detail="unauthorized")
