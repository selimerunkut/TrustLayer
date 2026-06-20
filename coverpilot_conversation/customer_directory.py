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
        customer_id="john",
        preferred_name="John",
        is_recurring=True,
        typically_travels_solo=True,
        usual_coverage_budget_usdc=45.0,
        usual_budget_description="Often uses about 45 USD for flight protection; treat as ~45 USDC when quoting.",
        common_concerns=("flight delays", "cancellation", "disruptions"),
        product_notes_for_broker=(
            "Prefers broad flight protection (delays and cancellations). Offer the usual ~45 USDC cap "
            "then confirm trip details before tools."
        ),
    ),
    "john smith",
    "john@trustlayer.demo",
    "jd",
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


_TRAVEL_PLANNING_HINT = re.compile(
    r"\b(travel|travell?ing|trip|flights?|flight|fly(ing)?|insur(ance|e)?|protect(ion)?|coverage|"
    r"delay|disrupt|cancellation|cancel(l(ed|ation)?)?|abroad|destination|itinerary|booking|"
    r"south america|north america|latin america|colombia|brazil|peru|europe|asia|africa|insure)\b",
    re.I,
)


def user_message_suggests_travel_planning(text: str) -> bool:
    """True when the traveler is asking about trips / flight protection (not a pure greeting)."""
    return bool(_TRAVEL_PLANNING_HINT.search(text or ""))


def session_crm_context_block(*, session_default_customer_id: str) -> str | None:
    """Authoritative CRM paragraph for the session customer (injected by the UI shell before the model runs)."""
    r = resolve_customer("", session_default_customer_id=session_default_customer_id)
    if not r.get("matched"):
        return None
    solo = "they usually travel solo" if r.get("typically_travels_solo") else "travel party size varies"
    name = r["preferred_name"]
    budget = float(r["usual_coverage_budget_usdc"])
    extra = str(r.get("usual_budget_description", "")).strip()
    return (
        "[TrustLayer kiosk — verified session CRM; authoritative for this chat]\n"
        f"Returning customer **{name}** ({solo}). "
        f"Typical flight-protection budget with us: **~{budget:.0f} USDC**. "
        f"{extra}\n"
        "You must greet them by first name and recall these preferences in your opening sentence for this reply. "
        "Do **not** ask for name or email to find their file."
    )


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
            "for flight protection and ask for a quick yes/no."
        ),
    }
