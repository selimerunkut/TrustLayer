# Hackathon Project Ideas

## Constraints

- **Build time:** 10 hours
- **Team:** AI coding agents
- **Model:** GPT-5.4 mini to keep inference costs low
- **Goal:** Build an original, demo-friendly agent-commerce product rather than another generic agent marketplace, escrow layer, or monitoring tool.

## Recommendation: NullProof

### One-line pitch

**A marketplace for bonded negative answers: agents are paid to search thoroughly and stake money behind claims that something could not be found within a clearly defined scope.**

### Example

> Are there any Berlin grants open today for a two-person climate startup?

A research agent:

1. Expands the question into multiple search strategies.
2. Searches the web and relevant official domains.
3. Publishes a coverage manifest showing queries, sources, domains, and timestamps.
4. Issues a bounded conclusion: **“No matching grant was found within this search scope.”**
5. Stakes a small USDC bond behind the conclusion.
6. Opens a short challenge period during which another agent can submit a valid counterexample.
7. Releases or transfers the bond according to the result.

### Important positioning

> **We do not prove that nothing exists. We make agents financially accountable for saying they found nothing.**

The claim must always be bounded by:

- Search time
- Sources and domains checked
- Query variants used
- Eligibility criteria
- Evidence standard

### Why it is original

A bounded web search found many products for citation verification, AI escrow, bounties, agent marketplaces, and change monitoring. It did **not** identify a direct product centered on bonded, challengeable negative search results.

This is not proof that no competitor exists, but it is a stronger novelty signal than the alternatives reviewed.

### Why it fits the hackathon

- Clearly demonstrates agent-to-agent commerce.
- Makes trust visible through evidence, staking, and challenges.
- Produces a dramatic live demo: one agent says “nothing found,” another tries to disprove it.
- Uses sponsor-aligned components without needing a production-grade protocol.
- Can be completed as a narrow vertical slice in 10 hours.

### 10-hour MVP

1. **Question form** — accept a bounded negative-search question.
2. **Research agent** — run several Tavily searches using generated query variants.
3. **Coverage report** — show queries, domains, sources, timestamps, and exclusion rules.
4. **Negative certificate** — GPT-5.4 mini generates a carefully bounded conclusion.
5. **Challenge agent** — independently attempts to find a qualifying counterexample.
6. **Resolution state machine** — `researching → bonded → challenged/uncontested → resolved`.
7. **Payment demo** — use Circle testnet wallets or the hackathon’s OOBE escrow flow.
8. **Public receipt** — display the claim, evidence, bond, challenge, and result on one page.

### Suggested demo script

1. Submit a question with an answer that is difficult to establish by absence.
2. Show the research agent searching several query variants and official sources.
3. Display its evidence coverage and bonded “not found” certificate.
4. Launch the challenger agent.
5. Resolve the bond based on whether a valid counterexample is found.
6. Show the permanent public receipt.

### Scores

| Criterion | Score |
|---|---:|
| Originality | 9/10 |
| 10-hour feasibility | 8/10 |
| Demo clarity | 9/10 |
| Sponsor alignment | 9/10 |

---

## Alternative 2: ClaimWarranty

### One-line pitch

**Agents sell individual research claims with citations, an expiry time, and a financial warranty that pays if the cited evidence does not support the claim or becomes invalid during the warranty period.**

### Product flow

1. A buyer requests a factual claim.
2. A research agent returns the claim, citation, evidence excerpt, confidence, and expiry time.
3. The agent attaches a small bond.
4. A verifier checks citation entailment and source availability.
5. If the claim fails the agreed test before expiry, the buyer receives the bond or refund.

### Novel wedge

Generic AI escrow and refund protocols already exist. The less crowded angle is a **claim-level, time-dependent warranty** rather than a warranty for an entire agent task.

### Competition risk

Adjacent products already cover parts of the idea:

- Citation verification
- AI-output escrow
- Agent payment disputes
- Refundable x402 transactions

It is therefore less original than NullProof, but still differentiated if the product stays focused on atomic claims and explicit validity periods.

### 10-hour MVP

- Claim request form
- Tavily research agent
- Citation entailment verifier
- Warranty duration and bond amount
- Circle testnet payment simulation
- Manual or automated dispute button
- Public claim receipt

### Scores

| Criterion | Score |
|---|---:|
| Originality | 7/10 |
| 10-hour feasibility | 9/10 |
| Demo clarity | 8/10 |

---

## Alternative 3: LeanReceipt

### One-line pitch

**After an agent completes a task, competing agents can earn a bounty by reproducing the accepted result at a meaningfully lower verified cost.**

### Product flow

1. An initial agent completes a task and publishes its result, model usage, latency, and cost.
2. A reproducibility bounty opens.
3. Other agents attempt the same task under the same acceptance tests.
4. A verifier checks semantic equivalence or test results.
5. The cheapest valid reproduction wins the bounty.
6. The winning execution becomes a reusable “lean receipt” for future routing.

### Novel wedge

Agent cost dashboards and model routers already exist. The differentiated mechanism is a **competitive, post-execution savings bounty** with an auditable reproduction receipt.

### Main risk

Defining objective equivalence is hard for open-ended tasks. The hackathon demo should use a testable task such as:

- Structured data extraction
- Code generation with tests
- Classification against a fixed evaluation set
- API workflow completion

### 10-hour MVP

- Submit task and baseline result
- Capture tokens, latency, and estimated cost
- Run two cheaper challenger agents
- Verify outputs against deterministic tests
- Rank valid reproductions by cost
- Simulate payout and publish the winning receipt

### Scores

| Criterion | Score |
|---|---:|
| Originality | 8/10 |
| 10-hour feasibility | 7/10 |
| Demo clarity | 8/10 |

---

## Ideas to Avoid

The following categories appear crowded and would likely look derivative unless given a much narrower mechanism:

1. **Generic agent marketplace** — many platforms already list, hire, or transact with agents.
2. **Human fallback for failed agents** — multiple services already let agents hire humans or post rescue tasks.
3. **Generic bounty platform** — bounty-based agent work is already represented by several products.
4. **Website or policy-change monitor** — Visualping and numerous specialized alternatives already cover this well.
5. **Generic AI escrow/refund protocol** — KAMIYO, Basilisk, x402r, and others already pursue this category.
6. **Wallet or reputation dashboard** — useful, but common and unlikely to stand out as the core hackathon idea.

## Competitive Research Summary

### Crowded: agent marketplaces and rescue networks

Examples found include eAgent, HiredByAgents, BotBounty, RoboRent, OIXA, Merxex, Hunazo, AgentPact, BotHire, Basilisk, and Cruxis.

### Crowded: website and policy-change monitoring

Examples include Visualping, OnChange, DeltaWatch, PageCrawl, RegWatch, and PolicyDiff.

### Crowded: generic escrow and output guarantees

Examples include KAMIYO, Basilisk, and x402r escrow.

### Partially crowded: citation verification and agent-cost optimization

SemanticCite validates citations, while products such as Dirr, AgentSpend, and Calibrait address agent costs, comparison, or routing. These are adjacent to ClaimWarranty and LeanReceipt but do not appear to implement their exact market mechanisms.

### Least crowded in this review

Exact and adjacent searches for products described as “proof of absence,” “negative answer certificate,” “bonded negative answer,” or a challenge market for negative web-search claims did not identify a direct equivalent to NullProof.

**Caution:** Search results can only establish bounded evidence of novelty, not prove that no similar product exists.

## Technical Feasibility Sources

- [Circle developer-controlled wallet quickstart](https://developers.circle.com/wallets/dev-controlled/create-your-first-wallet)
- [Circle Wallets documentation](https://developers.circle.com/wallets)
- [Tavily CLI documentation](https://docs.tavily.com/documentation/tavily-cli)
- [x402 FAQ](https://docs.x402.org/faq)
- [x402r escrow scheme](https://docs.x402r.org/x402-integration/escrow-scheme)

## Adjacent Products and Research

- [SemanticCite: LLM-Based Citation Verification](https://arxiv.org/abs/2511.16198)
- [Token Cost of Agentic Intelligence](https://arxiv.org/abs/2604.22750)
- [KAMIYO Protocol](https://protocol.kamiyo.ai/)
- [Basilisk](https://www.basilisk.exchange/)
- [Dirr](https://dirr.ai/)
- [AgentSpend](https://agentspend.org/)
- [Calibrait](https://calibrait.ai/)

## Final Decision

Build **NullProof**.

It has the best combination of novelty, sponsor alignment, visible agent-to-agent interaction, and a memorable 10-hour demo. Keep the product narrowly focused on one bounded question type rather than attempting a general research marketplace.
