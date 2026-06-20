"""Demo CRM: recurring customer profiles for personalized broker responses.

Production would replace this with a real identity / CRM lookup behind FastAPI.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class CustomerProfile:
    customer_id: str
    preferred_name: str
    is_recurring: bool
    typically_travels_solo: bool
    usual_coverage_budget_usdc: float
    usual_budget_description: str
    common_concerns: tuple[str, ...]
    product_notes_for_broker: str


_PROFILES: dict[str, CustomerProfile] = {}
_ALIASES: dict[str, str] = {}


def _register(profile: CustomerProfile, *aliases: str) -> None:
    _PROFILES[profile.customer_id.lower()] = profile
    for a in aliases:
        _ALIASES[a.strip().lower()] = profile.customer_id.lower()


_register(
    CustomerProfile(
        customer_id="vasiliy",
        preferred_name="Vasiliy",
        is_recurring=True,
        typically_travels_solo=True,
        usual_coverage_budget_usdc=40.0,
        usual_budget_description="Often allocates around 40 USD for travel protection (demo: treat as ~40 USDC).",
        common_concerns=("flight delays", "cancellation worry"),
        product_notes_for_broker=(
            "They often worry about cancellation; our demo product is delay-only—acknowledge "
            "the concern, then steer to delay coverage or decline."
        ),
    ),
    "vasiliy klyosov",
    "vasily",
    "vasiliy@trustlayer.demo",
    "vk",
)


def resolve_customer(identifier: str | None, *, session_default_customer_id: str) -> dict[str, Any]:
    """Resolve a customer id from free text, alias, or empty string (session default).

    Returns a JSON-serializable dict with either ``matched: true`` or ``matched: false``.
    """
    raw = (identifier or "").strip()
    key = raw.lower() if raw else session_default_customer_id.strip().lower()

    if not key:
        return {
            "matched": False,
            "message": "No customer hint and no session default; ask how they would like to be found on file.",
        }

    # direct id
    p = _PROFILES.get(key)
    if p:
        return _profile_to_dict(p)

    # alias -> id
    cid = _ALIASES.get(key)
    if cid:
        return _profile_to_dict(_PROFILES[cid])

    # fuzzy: first token name match
    token = re.split(r"[\s,@]+", key, maxsplit=1)[0]
    for pid, prof in _PROFILES.items():
        if pid.startswith(token) or prof.preferred_name.lower().startswith(token):
            return _profile_to_dict(prof)

    return {
        "matched": False,
        "message": f"No recurring profile matched {raw!r}. Proceed as a new guest; ask name if needed.",
    }


def _profile_to_dict(p: CustomerProfile) -> dict[str, Any]:
    return {
        "matched": True,
        "customer_id": p.customer_id,
        "preferred_name": p.preferred_name,
        "is_recurring": p.is_recurring,
        "typically_travels_solo": p.typically_travels_solo,
        "usual_coverage_budget_usdc": p.usual_coverage_budget_usdc,
        "usual_budget_description": p.usual_budget_description,
        "common_concerns": list(p.common_concerns),
        "product_notes_for_broker": p.product_notes_for_broker,
        "personalization_hint": (
            f"If they have not stated a budget yet, offer their usual ~{p.usual_coverage_budget_usdc:g} USDC "
            f"for delay coverage and ask for a quick yes/no."
        ),
    }
