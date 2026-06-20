"""TrustLayer static KB consult for ``policy_research`` (demo).

Reads ``KB/flight_attributes.md`` from the repository root and returns excerpts +
mock sub-tool trace. The broker must ground regulatory copy in this material—not
invent rules.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

_KB_RELATIVE = Path("KB") / "flight_attributes.md"

# Section anchors in KB/flight_attributes.md (keep in sync with the markdown file)
_MARK_RISK_FACTORS_START = "## 1. Flight Attributes"
_MARK_REGULATORY_CONTEXT_START = "## 2. Regulatory Context"
_MARK_EU_START = "# 3. Germany (EU) Flight Rules"
_MARK_CO_START = "# 4. Colombia Flight Rules"
_MARK_OTHER_SA_START = "# 5. Other South American Jurisdictions"
_MARK_ROUTES_START = "# 6. Germany ↔ Colombia Route Examples"
_MARK_PRICING_START = "# 7. Insurance Pricing Implications"


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _slice_between(text: str, start_needle: str, end_needle: str | None) -> str:
    i = text.find(start_needle)
    if i < 0:
        return ""
    start = i
    if not end_needle:
        return text[start:].strip()
    j = text.find(end_needle, start + len(start_needle))
    if j < 0:
        return text[start:].strip()
    return text[start:j].strip()


def _kb_text() -> str:
    path = _repo_root() / _KB_RELATIVE
    if not path.is_file():
        raise FileNotFoundError(f"KB missing at {path}")
    return path.read_text(encoding="utf-8")


def _trip_context(trip_digest: str) -> dict[str, Any]:
    t = trip_digest.lower()
    colombia = bool(
        re.search(
            r"\b(colombia|bogot[aá]|medell[ií]n|cali|cartagena|aerocivil|rac\s*3|"
            r"avianca|copa\s*airlines?|copa\b|wingo|latam|"
            r"bog|mde|clo|ctg|baq)\b",
            t,
        )
    )
    explicit_other_sa = bool(
        re.search(
            r"\b(brazil|brasil|s(ã|a)o paulo|rio de janeiro|anac|chile|santiago|"
            r"argentina|buenos aires|per[uú]|lima)\b",
            t,
        )
    )
    south_america_generic = bool(re.search(r"\b(south america|latin america)\b", t))
    eu_context = bool(
        re.search(
            r"\b(ryanair|eu261|schengen|europe|european|london|berlin|paris|frankfurt|"
            r"madrid|rome|munich|münchen|hamburg|germany|deutschland|bulgaria|sofia|varna|"
            r"eu\b|lufthansa|"
            r"easyjet|vueling|iberia|tap|klm|air france|swiss|austrian|"
            r"layover|connection|transfer|missed|"
            r"fra|muc|txl|ber|ams|cdg|mad|lhr|lgw|fco|bcn|lis|vie|zrh|sof)\b",
            t,
        )
    )
    connection_risk = bool(re.search(r"\b(layover|connection|transfer|miss)\b", t))
    compare_region = bool(
        re.search(
            r"\b(compare|comparison|across south america|each country|"
            r"other countries in south america)\b",
            t,
        )
    )
    return {
        "colombia_named": colombia,
        "explicit_other_sa": explicit_other_sa,
        "south_america_generic": south_america_generic,
        "eu_context": eu_context,
        "connection_risk": connection_risk,
        "compare_region": compare_region,
        # Back-compat aggregate used by older prompt wording
        "south_america_context": bool(
            colombia or explicit_other_sa or south_america_generic
        ),
    }


def _harvest_quotes(section: str, trip_digest: str, max_quotes: int = 6) -> list[str]:
    """Pull KB lines most relevant to the trip digest, ranked by keyword overlap.

    Scores each candidate line by how many trip-digest keywords it contains, then
    returns the top-N by score (across all sections). This avoids the old sequential
    early-exit that always returned quotes from the top of the EU block.
    """
    if not section.strip():
        return []

    keys = set(re.findall(r"[a-z]{4,}", trip_digest.lower()))
    keys.update(
        {
            "delay",
            "compensation",
            "hour",
            "eu",
            "cancellation",
            "connection",
            "missed",
            "261",
            "rac",
            "snack",
            "colombia",
            "bogot",
        }
    )

    signal_words = (
        "delay",
        "compens",
        "eu",
        "hour",
        "flight",
        "cancel",
        "connect",
        "miss",
        "261",
        "assistance",
        "rac",
        "snack",
        "phone",
        "€",
    )

    scored: list[tuple[int, str]] = []
    for line in section.splitlines():
        low = line.lower()
        stripped = line.strip()
        if len(stripped) < 12:
            continue
        if not any(w in low for w in signal_words):
            continue
        score = sum(1 for k in keys if k in low)
        if score > 0:
            scored.append((score, stripped))

    seen: set[str] = set()
    result: list[str] = []
    for _, line in sorted(scored, key=lambda x: -x[0]):
        if line not in seen:
            seen.add(line)
            result.append(line)
        if len(result) >= max_quotes:
            break
    return result


def run_policy_research(trip_digest: str) -> dict[str, Any]:
    """Load KB, select sections from ``trip_digest``, return JSON-serializable bundle."""
    digest = (trip_digest or "").strip()
    if not digest:
        raise ValueError("trip_digest must be non-empty")

    full = _kb_text()
    risk_factors_block = _slice_between(full, _MARK_RISK_FACTORS_START, _MARK_REGULATORY_CONTEXT_START)
    eu_block = _slice_between(full, _MARK_EU_START, _MARK_CO_START)
    col_block = _slice_between(full, _MARK_CO_START, _MARK_OTHER_SA_START)
    other_sa_block = _slice_between(full, _MARK_OTHER_SA_START, _MARK_ROUTES_START)
    routes_block = _slice_between(full, _MARK_ROUTES_START, _MARK_PRICING_START)
    pricing_block = _slice_between(full, _MARK_PRICING_START, None)

    ctx = _trip_context(digest)
    excerpts: dict[str, str] = {}

    # Section 1 — flight risk factors — always included so Betty can discuss route
    # reliability, timing, and operational exposure without inventing facts.
    if risk_factors_block:
        excerpts["flight_risk_factors"] = risk_factors_block[:1500]

    include_eu = ctx["eu_context"] or ctx["connection_risk"]
    include_colombia_section = ctx["colombia_named"]
    include_other_sa_section = ctx["explicit_other_sa"] or (
        ctx["compare_region"] and ctx["south_america_generic"]
    )
    include_route_examples = ctx["colombia_named"] and ctx["eu_context"]

    if include_eu:
        excerpts["eu261_germany"] = eu_block[:6000]
    if include_colombia_section:
        excerpts["colombia_rac3"] = col_block[:6000]
    if include_other_sa_section:
        excerpts["other_south_american_jurisdictions"] = other_sa_block[:5000]
    if include_route_examples:
        excerpts["germany_colombia_route_examples"] = routes_block[:5000]
    if excerpts:
        excerpts["insurance_pricing_implications"] = pricing_block[:3500]
    else:
        # Generic digest: still give the broker grounded material
        excerpts["eu261_germany"] = eu_block[:3500]
        excerpts["colombia_rac3"] = col_block[:3500]
        excerpts["insurance_pricing_implications"] = pricing_block[:2500]

    combined_for_quotes = "\n\n".join(excerpts.values())
    verbatim = _harvest_quotes(combined_for_quotes, digest)[:8]

    omit_list: list[str] = []
    if include_colombia_section and not include_other_sa_section:
        omit_list = ["Brazil", "Chile", "Argentina", "Peru"]

    narration_scope = {
        "lead_with": [],
        "also_cover": [],
        "do_not_tour_unless_in_excerpts": omit_list,
    }
    if include_colombia_section:
        narration_scope["lead_with"].append("Colombia (RAC 3 / Aerocivil)")
    if include_eu:
        narration_scope["lead_with"].append("Germany / EU (EU Regulation 261/2004)")
    if include_route_examples:
        narration_scope["also_cover"].append(
            "Germany ↔ Colombia route table (which leg is EU261 vs RAC 3)"
        )
    if include_other_sa_section:
        narration_scope["also_cover"].append(
            "Other South American jurisdictions named in the digest"
        )
    if include_other_sa_section and not include_colombia_section and not include_eu:
        narration_scope["lead_with"].append(
            "South America — jurisdictions present in other_south_american_jurisdictions excerpt"
        )

    trace = [
        "[mock] kb_load → flight_attributes.md",
        "[mock] kb_slice → headings: flight risk factors, EU Germany, Colombia RAC 3, "
        "optional other SA, optional DE↔CO examples, pricing tail",
        "[mock] kb_quote_harvest → top-scored line citations for broker narration",
    ]

    connection_note = ""
    if ctx["connection_risk"] and eu_block:
        connection_note = (
            "KB highlights for connections (EU legs): delay is measured at **final arrival**; "
            "short Ryanair segments that cause a missed long-haul can still engage EU261 **if** the "
            "itinerary qualifies as EU-regulated (departing EU / EU carrier into EU—see KB table). "
            "Missed-connection **rebooking costs** are a separate bucket from fixed delay cash in KB "
            "insurance pricing section."
        )

    return {
        "kb_relative_path": str(_KB_RELATIVE).replace("\\", "/"),
        "mock_subtool_trace": trace,
        "trip_keyword_flags": {
            "eu_context": ctx["eu_context"],
            "south_america_context": ctx["south_america_context"],
            "connection_risk": ctx["connection_risk"],
            "colombia_named": ctx["colombia_named"],
            "explicit_other_sa": ctx["explicit_other_sa"],
        },
        "narration_scope": narration_scope,
        "excerpts": excerpts,
        "verbatim_kb_quotes": verbatim,
        "broker_narration_hints": [
            "Ground every regulatory claim in returned `excerpts` / `verbatim_kb_quotes`—cite EU261 "
            "or RAC 3 using KB wording.",
            "Use `flight_risk_factors` excerpt to discuss route characteristics and operational risk "
            "in plain language (departure timing, airline reliability, weather exposure) without inventing stats.",
            "Follow `narration_scope`: do **not** narrate Brazil/Chile/Argentina/Peru when "
            "`do_not_tour_unless_in_excerpts` lists them unless the user or excerpts explicitly "
            "opened those jurisdictions.",
            "When both EU and Colombia appear, prefer the **Germany ↔ Colombia route examples** "
            "excerpt (if present) to explain which leg uses which regime.",
            "Use `insurance_pricing_implications` pricing bands to explain *why* the premium is "
            "at its level (risk tier, regulatory exposure)—cite the tier name from the KB.",
            "Light humor is allowed only as **hyperbolic illustration** of numbers already in the "
            "KB (e.g. RAC 3 snack + short call vs EU261 € band)—label it as playful KB contrast, "
            "never as legal advice.",
        ],
        "connection_and_missed_flight_kb_note": connection_note or None,
        "raw_char_count": len(full),
    }


def run_policy_research_json(trip_digest: str) -> str:
    return json.dumps(run_policy_research(trip_digest), ensure_ascii=False)
