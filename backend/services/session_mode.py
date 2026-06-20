from collections.abc import Mapping
import os

from backend.schemas import SessionMode
from backend.services.base_sepolia import base_sepolia_ready as base_sepolia_config_ready, load_base_sepolia_config


def decide_session_mode(*, circle_ready: bool, base_sepolia_ready: bool, explicit_mock_only: bool = False) -> SessionMode:
    if explicit_mock_only:
        return SessionMode.MOCK_ONLY
    if circle_ready and base_sepolia_ready:
        return SessionMode.LIVE
    return SessionMode.DEGRADED


def _flag_from_env(env: Mapping[str, str], key: str) -> bool:
    value = env.get(key)
    if value is None:
        return False
    return value.strip().lower() in {"1", "true", "yes", "on", "live"}


def preflight_session_mode(env: Mapping[str, str] | None = None) -> SessionMode:
    current_env = os.environ if env is None else env
    explicit_mock_only = _flag_from_env(current_env, "COVERPILOT_MOCK_ONLY")
    circle_ready = _flag_from_env(current_env, "CIRCLE_READY") and bool(
        current_env.get("CIRCLE_API_KEY", "").strip() and current_env.get("CIRCLE_WALLET_ID", "").strip()
    )
    base_sepolia_config = load_base_sepolia_config(current_env)
    base_sepolia_ready = _flag_from_env(current_env, "BASE_SEPOLIA_READY") and base_sepolia_config_ready(base_sepolia_config)
    return decide_session_mode(
        circle_ready=circle_ready,
        base_sepolia_ready=base_sepolia_ready,
        explicit_mock_only=explicit_mock_only,
    )


def fallback_mode_label(session_mode: SessionMode) -> str:
    return {
        SessionMode.LIVE: "real",
        SessionMode.DEGRADED: "degraded",
        SessionMode.MOCK_ONLY: "mocked",
    }[session_mode]
