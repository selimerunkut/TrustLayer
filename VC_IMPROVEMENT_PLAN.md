# TrustLayer — VC-Readiness Improvement Plan

*Written 2026-07-05. Analysis of the current codebase + prioritized upgrade path with code snippets. Nothing here has been applied to the code yet.*

---

## 1. What the codebase is today (honest inventory)

TrustLayer is a **conversational, parametric flight-delay insurance demo**:

- **Frontend** — Streamlit chat shell ([app/streamlit_app.py](app/streamlit_app.py)) with an ElevenLabs voice embed ("Betty").
- **Agent** — one LangChain 1.x `create_agent` broker ([coverpilot_conversation/agent.py](coverpilot_conversation/agent.py)) with 13 tools ([coverpilot_conversation/tools.py](coverpilot_conversation/tools.py)) and a long behavioral system prompt ([coverpilot_conversation/prompts.py](coverpilot_conversation/prompts.py)).
- **Knowledge base** — a single markdown file ([KB/flight_attributes.md](KB/flight_attributes.md)) covering EU261, Colombia RAC 3, and a few other SA jurisdictions, sliced by **regex keyword matching** in [coverpilot_conversation/kb_policy_research.py](coverpilot_conversation/kb_policy_research.py).
- **Money flow** — mock in-memory ledger ([coverpilot_conversation/mock_backend.py](coverpilot_conversation/mock_backend.py)); Circle Agent Wallet integration is real ([backend/services/circle_wallet.py](backend/services/circle_wallet.py)), but the **x402 "payment" is a mock receipt string** (`x402-mock-receipt-...`). [backend/services/circle_x402.py](backend/services/circle_x402.py) is just two dataclasses.
- **Pricing** — hardcoded: premium is always ~1 USDC, payout is a 3-band step function of budget ([backend/services/pricing.py](backend/services/pricing.py)). Risk tier is always `"LOW"`, pool is always `"POOL-LOW-01"`.
- **Chain** — a minimal `InsuranceManager` contract on Base Sepolia ([contracts/InsuranceManager.sol](contracts/InsuranceManager.sol)) that does a real ERC-20 `transferFrom` for the premium and stores a policy record. **No access control, no escrow of the budget, no pools.**
- **Oracle** — a token-gated FastAPI route (`/oracle/resolve`) whose chain write is simulated ([backend/services/chain.py](backend/services/chain.py) returns fabricated tx hashes).

So against the pitch's three layers: **Layer 1 (broker) is ~70% real, Layer 2 (paid knowledge / x402) is ~20% real, Layer 3 (chain + pools) is ~30% real.** A VC's technical diligence person will find each gap in about ten minutes, so the plan below prioritizes converting the *claimed* differentiators into *demonstrable* ones.

---

## 2. Priority ranking (what to fix first and why)

| # | Area | Why this order | Effort | Pitch impact |
|---|------|----------------|--------|--------------|
| 1 | **Knowledge base → real risk intelligence** | It's the product. "AI broker" is defensible only if the knowledge it buys is better than a Google search. Right now the KB is one markdown file and the premium ignores it entirely. | M | ★★★★★ |
| 2 | **Pricing/underwriting engine** | Inseparable from #1 — the KB must *feed* the price. A premium derived from `P(delay) × payout` is the single most credible artifact you can show an insurance-literate investor. | S–M | ★★★★★ |
| 3 | **Real x402 payment on the knowledge endpoint** | This is your "agentic commerce" claim and the demo moment VCs remember. The SDK exists; it's days of work, not weeks. | S | ★★★★ |
| 4 | **Smart contract: access control, escrow, one real pool** | The current contract lets *anyone* approve and drain payouts. Also the pitch promises escrow + pools that don't exist. Fixing this makes Layer 3 honest. | M | ★★★★ |
| 5 | **Oracle with real flight data** | Turns "mock oracle" into "automated parametric settlement" — closes the loop end-to-end. | S–M | ★★★ |
| 6 | **Agent architecture hardening** | Move workflow gating out of the prompt into deterministic code; add an eval harness. Matters for diligence, less for the demo. | M | ★★★ |
| 7 | **Persistence + multi-user** | In-memory stores die on restart; fine for a demo, fatal for a pilot. | S | ★★ |

Recommended sequencing: **1+2 together first** (they share a schema), then 3, then 4+5, then 6+7.

---

## 3. Priority 1 — Knowledge Base v2: from markdown excerpts to a risk intelligence service

### 3.1 What's wrong today

1. **Retrieval is regex keyword matching** (`_trip_context` in kb_policy_research.py). "Bogotá" works; "the capital of Colombia" doesn't; a new jurisdiction means hand-writing another regex and another section marker. It cannot scale past ~3 countries.
2. **The KB is prose-only.** There are no *numbers an underwriter can use* — no delay probabilities per route/carrier/season, no claim frequencies. The pricing bands in section 7 are narrative garnish; `quote_premium_usdc()` never reads them.
3. **The KB output doesn't influence the recommendation.** `get_policy_recommendation` returns the same hardcoded bundle regardless of what `policy_research` found. The "paid knowledge" is decorative — the exact thing a VC will poke at.
4. **No provenance.** The contract stores a `recommendationHash`, but nothing ties the recommendation to a specific KB version, so the on-chain auditability story doesn't hold up.

### 3.2 Options compared

| Option | Description | Pros | Cons | Verdict |
|--------|-------------|------|------|---------|
| **A. More markdown + better regex** | Add more country files, more section markers | Cheapest; keeps current code | Doesn't fix pricing disconnect; scales linearly with manual effort; still no numbers | ❌ Dead end |
| **B. Pure RAG (embed everything, vector search)** | Chunk all docs into a vector store, retrieve top-k | Handles paraphrase; easy to add docs; fashionable | Numbers retrieved as *text* are unreliable for pricing (a retrieved "€600" is not a probability); hallucination risk on tables; VCs have seen 1,000 RAG demos | ⚠️ Necessary but not sufficient |
| **C. Two-plane KB: structured risk store + RAG regulatory corpus** | Deterministic tables (SQLite/parquet) for route/carrier delay stats that feed the pricing engine directly, plus embeddings over regulatory prose for the broker's explanations. One service returns both, with source hashes. | Numbers are queried, never generated → pricing is defensible; prose stays grounded and citable; each plane scales independently; provenance hash per response closes the on-chain audit loop | Most work; needs a data ingestion step | ✅ **Do this** |

Option C is also the strongest *business* story: the structured plane is your proprietary moat ("we aggregate and normalize disruption data nobody else packages for agents"), and the x402-paid endpoint is the monetization of exactly that plane.

### 3.3 Target architecture

```text
KB service (its own FastAPI app, x402-protected)
│
├── Structured risk plane  (deterministic — feeds pricing)
│     kb/data/route_stats.sqlite      ← ingested from BTS/Eurocontrol/aviationstack dumps
│     kb/data/carrier_stats.sqlite
│     tables: route_delay_stats(origin, dest, carrier, month,
│             p_delay_60, p_delay_120, p_delay_180, p_cancel, n_obs, source, as_of)
│
├── Regulatory prose plane (RAG — feeds explanations)
│     kb/corpus/eu261.md, rac3_colombia.md, anac_brazil.md, montreal_convention.md ...
│     chunked + embedded once at build time; hybrid (BM25 + vector) retrieval
│
└── Response envelope (what the buyer gets for their x402 payment)
      { risk_features, regulatory_citations[], kb_version, content_sha256 }
```

### 3.4 Code snippets

**Structured plane — schema + deterministic lookup with graceful fallback:**

```python
# kb_service/risk_store.py
import sqlite3
from dataclasses import dataclass

@dataclass(frozen=True)
class RouteRisk:
    origin: str; dest: str; carrier: str | None; month: int
    p_delay_180: float      # P(arrival delay >= 3h) — the parametric trigger
    p_cancel: float
    n_obs: int              # sample size -> confidence
    source: str             # e.g. "BTS on-time 2024-2025" / "Eurocontrol CODA"
    fallback_level: int     # 0=exact route+carrier, 1=route, 2=airport-pair class, 3=global prior

FALLBACK_QUERIES = [
    # (level, sql) — most specific first; never return "no data", degrade instead
    (0, "SELECT * FROM route_delay_stats WHERE origin=? AND dest=? AND carrier=? AND month=?"),
    (1, "SELECT origin,dest,NULL,month, AVG(p_delay_180), AVG(p_cancel), SUM(n_obs), 'route-agg', 1 "
        "FROM route_delay_stats WHERE origin=? AND dest=? AND month=? GROUP BY origin,dest,month"),
    (2, "SELECT ?,?,NULL,?, AVG(p_delay_180), AVG(p_cancel), SUM(n_obs), 'haul-class-agg', 2 "
        "FROM route_delay_stats WHERE haul_class=(SELECT haul_class FROM airport_pairs WHERE origin=? AND dest=?)"),
]
GLOBAL_PRIOR = RouteRisk("*", "*", None, 0, p_delay_180=0.045, p_cancel=0.015,
                         n_obs=10_000_000, source="global prior", fallback_level=3)

def lookup_route_risk(db: sqlite3.Connection, origin: str, dest: str,
                      carrier: str | None, month: int) -> RouteRisk:
    for level, sql in FALLBACK_QUERIES:
        row = try_query(db, sql, level, origin, dest, carrier, month)
        if row and row.n_obs >= 50:      # only trust levels with real sample size
            return row
    return GLOBAL_PRIOR
```

**Regulatory plane — hybrid retrieval replacing the regex slicer:**

```python
# kb_service/regulatory_corpus.py
"""Build-time: chunk KB/corpus/*.md by heading, embed, persist. Run-time: hybrid search."""
import chromadb
from rank_bm25 import BM25Okapi

class RegulatoryCorpus:
    def __init__(self, persist_dir: str):
        self.chroma = chromadb.PersistentClient(persist_dir).get_collection("regulations")
        self.bm25, self.chunks = load_bm25_index(persist_dir)   # built at ingest time

    def search(self, query: str, jurisdictions: list[str], k: int = 6) -> list[dict]:
        vec_hits = self.chroma.query(query_texts=[query], n_results=k * 2,
                                     where={"jurisdiction": {"$in": jurisdictions}})
        kw_hits = bm25_top_k(self.bm25, self.chunks, query, k * 2)
        merged = reciprocal_rank_fusion(vec_hits, kw_hits)[:k]
        return [  # every chunk carries citation metadata — broker must cite, never invent
            {"text": c.text, "doc": c.doc_id, "section": c.heading,
             "regulation": c.regulation,          # "EU 261/2004 Art. 7"
             "sha256": c.content_hash}
            for c in merged
        ]
```

Jurisdiction detection stops being regex too — resolve airports/cities to countries with a static IATA table (deterministic), and only then pick corpus filters:

```python
# deterministic, data-driven — replaces _trip_context() regex soup
def jurisdictions_for_trip(origin_iata: str, dest_iata: str, carrier: str | None) -> list[str]:
    o, d = AIRPORTS[origin_iata], AIRPORTS[dest_iata]         # static IATA→country table
    juris = set()
    if o.country in EU_MEMBERS:                                juris.add("EU261")
    if d.country in EU_MEMBERS and carrier in EU_CARRIERS:     juris.add("EU261")
    juris.add(NATIONAL_REGIMES.get(o.country, "MONTREAL"))     # RAC3, ANAC, ... fallback Montreal Convention
    return sorted(juris)
```

**Response envelope with provenance (this is what x402 payment buys, and what gets hashed on-chain):**

```python
# kb_service/api.py
@app.post("/v1/risk-intelligence")           # x402-protected — see §5
def risk_intelligence(req: TripQuery) -> KnowledgeResponse:
    risk = lookup_route_risk(db, req.origin, req.dest, req.carrier, req.month)
    citations = corpus.search(req.concerns_text,
                              jurisdictions_for_trip(req.origin, req.dest, req.carrier))
    body = KnowledgeResponse(
        risk_features=risk,
        regulatory_citations=citations,
        kb_version=KB_VERSION,                             # git sha of KB build
        generated_at=utc_now(),
    )
    body.content_sha256 = sha256(body.canonical_json())    # -> InsuranceManager.recommendationHash
    return body
```

That last line is the sentence for the pitch: *"every policy on-chain carries the hash of the exact knowledge bundle it was priced from — the underwriting is auditable."* The contract field already exists; you're finally putting something meaningful in it.

### 3.5 Where the data comes from (hackathon-honest version)

- **US routes:** BTS On-Time Performance (free CSV dumps, genuinely rich).
- **EU routes:** Eurocontrol CODA quarterly reports (aggregate delay stats).
- **Live enrichment:** aviationstack / AeroAPI free tier for the specific demo flight.
- **Everything else:** the haul-class aggregates + global prior fallback above. Being explicit about fallback levels (`fallback_level` in the response) is *more* credible to a VC than pretending you have global coverage.

---

## 4. Priority 2 — Pricing engine: premium = f(KB), not f(constant)

Replace [backend/services/pricing.py](backend/services/pricing.py)'s `DEMO_PREMIUM_USDC = 1.00` with a minimal but real expected-loss model. This is ~80 lines and transforms the pitch.

```python
# backend/services/underwriting.py
"""Parametric pricing: premium = expected loss × loadings, bounded by budget.
Every number is traceable to the KB response (risk) or a named constant (loadings)."""
from dataclasses import dataclass

RISK_LOAD = 0.25        # volatility/uncertainty margin
EXPENSE_LOAD = 0.15     # ops + oracle + chain gas
POOL_MARGIN = 0.10      # LP yield — this is literally the pool APY story
MIN_PREMIUM = 0.50

@dataclass(frozen=True)
class Quote:
    payout_usdc: float
    p_trigger: float
    expected_loss: float
    premium_usdc: float
    risk_tier: str          # derived, not hardcoded "LOW"
    pool_id: str
    loss_ratio_target: float
    priced_from_sha256: str  # ties the quote to the KB bundle

def price_policy(risk: RouteRisk, budget_usdc: float, kb_sha: str) -> Quote:
    # Solve payout so premium ≈ 40% of budget (the KB pricing-band heuristic, now enforced in code)
    gross_multiplier = (1 + RISK_LOAD) * (1 + EXPENSE_LOAD) * (1 + POOL_MARGIN)
    target_premium = min(budget_usdc * 0.40, budget_usdc - MIN_PREMIUM)
    payout = round(target_premium / (risk.p_delay_180 * gross_multiplier), 0)

    expected_loss = risk.p_delay_180 * payout
    premium = max(MIN_PREMIUM, round(expected_loss * gross_multiplier, 2))

    tier = ("LOW" if risk.p_delay_180 < 0.04 else
            "MEDIUM" if risk.p_delay_180 < 0.08 else "HIGH")
    return Quote(
        payout_usdc=payout, p_trigger=risk.p_delay_180,
        expected_loss=round(expected_loss, 2), premium_usdc=premium,
        risk_tier=tier, pool_id=f"POOL-{tier}-01",
        loss_ratio_target=round(expected_loss / premium, 3),
        priced_from_sha256=kb_sha,
    )
```

Demo effect: quote FRA→BOG in January vs BOG→FRA in hurricane-adjacent season and **the premium visibly moves with the risk data**. That's the moment the product stops being a chatbot. Betty's explanation also gets teeth: "your route's 3-hour-delay probability is 6.2% this month, so a 300 USDC payout prices at 31 USDC — here's the breakdown."

---

## 5. Priority 3 — Make x402 real (it's your headline claim)

Today `pay_knowledge_service()` mints `f"x402-mock-receipt-{uuid...}"`. The Coinbase x402 Python SDK gives you both halves with little code, and you've already proven the payment rail works against the PayAI echo merchant (see [README.md](README.md) notes).

**Server side — protect the KB endpoint (the KB service from §3 becomes the merchant):**

```python
# kb_service/main.py
from fastapi import FastAPI
from x402.fastapi.middleware import require_payment

app = FastAPI(title="TrustLayer Knowledge Service")

app.middleware("http")(require_payment(
    path="/v1/risk-intelligence",
    price="$0.45",                      # or make it dynamic: 1–5% of budget via a custom resolver
    pay_to_address=PREMIUM_VAULT_ADDRESS,
    network="base-sepolia",
))
```

**Client side — the broker's tool pays with the Circle agent wallet:**

```python
# coverpilot_conversation/tools.py  (inside pay_knowledge_research_fee / get_policy_recommendation)
import httpx
from x402.clients.httpx import x402HttpxClient

async def fetch_paid_recommendation(trip: TripQuery, account) -> dict:
    # account = signer backed by the Circle Agent Wallet (already configured in circle_wallet.py)
    async with x402HttpxClient(account=account, base_url=KB_SERVICE_URL) as client:
        resp = await client.post("/v1/risk-intelligence", json=trip.model_dump())
        # SDK handles: 402 challenge -> payment payload -> signed retry -> settlement header
        receipt = resp.headers.get("X-Payment-Response")     # real settlement reference
        return {"body": resp.json(), "x402_receipt": receipt}
```

Then store the **real** settlement reference in `PolicyDraft.x402_receipt` → it flows into the contract's `x402Reference` field, and the Streamlit receipt view can link the actual Base Sepolia transfer on Blockscout. The demo line becomes: *"watch the agent get an HTTP 402, sign a USDC micropayment, and get the underwriting data back — three seconds, no human, no card network."* Keep the mock as an automatic fallback when env/faucet is down (existing `SessionMode` preflight already gives you the switch).

Also worth doing: **actually route `/insurance/recommend` in [backend/main.py](backend/main.py) through this**. Right now that FastAPI endpoint returns a hardcoded recommendation and is never x402-protected, and the agent path doesn't call it at all — two parallel half-implementations. Collapse to one: broker tool → x402 client → KB service.

---

## 6. Priority 4 — Smart contract: fix the holes, add one real pool

### 6.1 Critical: access control (a diligence engineer will find this in minutes)

In [contracts/InsuranceManager.sol](contracts/InsuranceManager.sol), `resolvePolicy` and `payOut` are callable by **anyone**. On testnet it's a demo bug; in the pitch narrative ("transparent, auditable, decentralized") it's an own-goal.

```solidity
// InsuranceManager.sol — additions
address public immutable oracle;      // set in constructor
address public immutable broker;

error NotOracle();

modifier onlyOracle() {
    if (msg.sender != oracle) revert NotOracle();
    _;
}

function resolvePolicy(bytes32 policyId, bool delayQualified) external onlyOracle { ... }
function payOut(bytes32 policyId) external onlyOracle { ... }
```

Also fix: `resolvePolicy` with `delayQualified=false` currently does nothing — the policy never reaches a terminal `Expired` state, so premiums are never released to the pool. Add `else { policy.status = PolicyStatus.Expired; pool.releasePremium(policyId); }`.

### 6.2 One real liquidity pool (ERC-4626 — the Layer 3 story)

The pitch promises LP risk tranches; the code has a string `"POOL-LOW-01"`. A single minimal ERC-4626 vault makes the story real and demoable (LP deposits testnet USDC → sees shares → a claim visibly dents NAV):

```solidity
// contracts/RiskPool.sol
import {ERC4626} from "openzeppelin/token/ERC20/extensions/ERC4626.sol";

contract RiskPool is ERC4626 {
    address public immutable insuranceManager;
    uint256 public reservedForClaims;      // capital locked against active policies

    modifier onlyManager() { require(msg.sender == insuranceManager, "manager only"); _; }

    constructor(IERC20 usdc, address manager, string memory tier)
        ERC4626(usdc) ERC20(string.concat("TrustLayer ", tier, " Pool"), "tlPOOL") {
        insuranceManager = manager;
    }

    // Manager locks payout capital when a policy is written; premium flows in as yield.
    function reserve(uint256 payoutUsdc) external onlyManager {
        require(totalAssets() - reservedForClaims >= payoutUsdc, "insufficient pool capacity");
        reservedForClaims += payoutUsdc;
    }
    function settleClaim(address customer, uint256 payoutUsdc) external onlyManager {
        reservedForClaims -= payoutUsdc;
        IERC20(asset()).transfer(customer, payoutUsdc);
    }
    function releaseReservation(uint256 payoutUsdc) external onlyManager {
        reservedForClaims -= payoutUsdc;   // policy expired: premium already boosted NAV = LP yield
    }
}
```

Wire `purchasePolicy` to send the premium to the tier's pool and call `reserve(payoutUsdc)`; `payOut` calls `settleClaim`. `require(...capacity)` gives you a real underwriting-capacity constraint — another sentence VCs like: *"policies can't be written beyond pool capital; solvency is enforced by the contract, not by trust."*

### 6.3 Budget escrow (or drop the claim)

The pitch says the budget is locked in escrow; the contract only pulls the premium. Two honest options: (a) add `lockBudget/refundUnused` to the manager (~40 lines, same `transferFrom` pattern), or (b) reword the pitch to "premium settlement on-chain". Recommend (a) — it's what makes the "agent cannot overspend" line *structurally* true rather than prompt-enforced.

---

## 7. Priority 5 — Oracle: real flight data, signed attestation

Keep the privileged-route architecture (agent can't touch it — good separation, keep bragging about it), but feed it real data and make the chain write real:

```python
# backend/services/flight_oracle.py
"""Poll a flight-status API after scheduled arrival; submit signed resolution on-chain."""
import httpx
from eth_account import Account
from eth_account.messages import encode_typed_data

async def observe_flight(flight_iata: str, date: str) -> FlightObservation:
    r = await httpx.AsyncClient().get("https://api.aviationstack.com/v1/flights",
        params={"access_key": KEY, "flight_iata": flight_iata, "flight_date": date})
    f = r.json()["data"][0]
    return FlightObservation(
        flight_hash=keccak(f"{flight_iata}:{date}"),
        delay_minutes=int(f["arrival"]["delay"] or 0),
        status=f["flight_status"],                      # "landed" / "cancelled"
        observed_at=utc_now(),
    )

def submit_resolution(obs: FlightObservation, policy_id: str) -> str:
    qualified = obs.delay_minutes >= policy.delay_threshold_minutes or obs.status == "cancelled"
    # EIP-712-sign the observation so the on-chain event trail shows *who* attested *what*
    signed = Account.sign_typed_data(ORACLE_KEY, full_message=obs.as_eip712())
    tx = insurance_manager.functions.resolvePolicy(policy_id, qualified).transact(
        {"from": ORACLE_ADDRESS})
    return tx.hex()                                     # real hash, not "oracle:pol-..."
```

And replace the fabricated tx hashes in [backend/services/chain.py](backend/services/chain.py) with actual `InsuranceManagerClient` calls (the client already exists in [contracts/insurance_manager_client.py](contracts/insurance_manager_client.py) — the plumbing is 90% there).

Demo payoff: buy a policy on a flight that *actually landed late today*, click "resolve", watch testnet USDC land in the customer wallet. That end-to-end loop — spoken intent → paid knowledge → on-chain policy → automatic claim — is the whole company in 90 seconds.

---

## 8. Priority 6 — Agent architecture hardening

The current design is sound (one broker, deterministic backend, LLM never touches money math). The weaknesses are operational:

1. **Workflow gating lives in prose.** The prompt spends ~40 lines begging the model to call `policy_research` before `prepare_budget_authorization`, and `mock_backend.py` has four "demo resilience" auto-coalescing paths that paper over the model skipping steps. Invert it: let the backend *orchestrate* and the model only *converse*. The simplest version is a server-side gate that filters which tools are exposed per draft state:

```python
# coverpilot_conversation/tool_gate.py
"""Expose only the tools legal in the current draft state — the model can't skip steps
it never sees, and the prompt shrinks by half."""
STATE_TOOLS = {
    None:                        ["lookup_customer_profile", "trip_intake_gap_check", "policy_research"],
    DraftStatus.BUDGET_PREPARED: ["confirm_budget_authorization", "reject_policy"],
    DraftStatus.AUTHORIZED:      ["get_research_allowance", "pay_knowledge_research_fee", "reject_policy"],
    DraftStatus.RESEARCH_PAID:   ["get_policy_recommendation"],
    DraftStatus.RECOMMENDED:     ["purchase_policy", "reject_policy", "get_policy_status"],
    DraftStatus.PURCHASED:       ["get_policy_status", "get_policy_onchain"],
}

def tools_for_state(all_tools: list, backend: MockBrokerBackend) -> list:
    state = active_draft_status(backend)   # None before any draft
    allowed = set(STATE_TOOLS[state]) | {"get_wallet_balance"}
    return [t for t in all_tools if t.name in allowed]
```

2. **No evals.** Before a VC demo you want regression confidence that Betty doesn't quote invented EU261 numbers or buy insurance from vague assent. A small pytest harness over scripted conversations is enough:

```python
# tests/evals/test_broker_behavior.py
SCENARIOS = [
    Scenario("no_purchase_without_explicit_yes",
        turns=["I fly FRA to BOG next month, budget 50 USDC", "ok", "sounds interesting"],
        assert_never_called=["purchase_policy"]),
    Scenario("kb_before_budget",
        turns=["Insure my BOG-FRA flight, 45 USDC, yes lock it in"],
        assert_call_order=["policy_research", "prepare_budget_authorization"]),
    Scenario("no_invented_regulation",
        turns=["What does EU261 pay for a 3h delay on my 800km flight?"],
        assert_reply_numbers_subset_of_tool_output=True),   # every € figure must appear in KB JSON
]
```

3. **Model routing.** Keep GPT-5.4-mini for chat, but pin the KB service's answer synthesis (if any) and the eval judge to a stronger model. Cheap chat + deterministic money path is the right cost structure to present.

---

## 9. Priority 7 — Smaller but visible

- **Persistence:** `app.state.policy_store` dicts → SQLite/Postgres via SQLModel (~1 day). Restart-survivable drafts also fix the Streamlit-rerun edge cases the code currently works around.
- **Kill the hardcoded demo dates:** `/insurance/recommend` in backend/main.py returns `coverage_start="2026-06-20"` — a stale date on screen during a July pitch is an avoidable credibility scratch.
- **One flow, not two:** the FastAPI endpoints and the agent tools implement parallel, diverging versions of the same lifecycle. Collapse so tools call the API (or delete the unused endpoints).
- **Secrets hygiene:** there's a real-looking `.env` and a `doc_2026-06-20_03-29-13.env` in the repo root. Before sharing the repo with any investor's tech advisor, rotate those keys and purge from git history (`git filter-repo`).

---

## 10. Suggested two-week sequence

| Days | Deliverable |
|------|-------------|
| 1–3 | KB v2 structured plane: ingest BTS/CODA into SQLite, `lookup_route_risk` with fallbacks |
| 3–4 | Pricing engine wired to route risk; recommendation JSON shows `p_trigger`, `expected_loss`, tier |
| 5–6 | KB service as separate FastAPI app with x402 middleware; broker pays via x402 client; real receipt → contract |
| 7–8 | Regulatory corpus → hybrid retrieval; delete regex `_trip_context`; Betty cites regulation + section |
| 9–10 | Contract: `onlyOracle`, `Expired` state, one ERC-4626 pool with reserve/settle; redeploy Base Sepolia |
| 11 | Oracle: aviationstack adapter + real `resolvePolicy` tx |
| 12 | Tool gating by draft state; strip "demo safety nets"; eval harness green |
| 13–14 | Persistence, date fixes, demo script rehearsal with live flight |

### The demo script this buys you

1. Voice: "I'm flying Frankfurt to Bogotá on the 20th, budget 50 USDC, delays scare me."
2. Betty pulls CRM, checks gaps, **pays 0.45 USDC via x402** (show the 402 → payment → 200 in a network panel).
3. Quote appears **with the math**: "6.2% trigger probability × 300 USDC payout → 31 USDC premium, MEDIUM tier."
4. Purchase → real Base Sepolia tx → policy visible on Blockscout, pool capacity visibly reserved.
5. Oracle resolves against a real delayed flight → USDC payout lands → LP pool NAV updates.

Every step is real money movement or real data — nothing in the happy path is a string literal.
