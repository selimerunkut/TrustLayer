# CoverPilot: Agentic P2P Travel Insurance

## Hackathon Scope

- **Insurance product:** Parametric flight-delay insurance
- **Customer experience:** Conversational and designed for non-crypto-native travelers
- **Frontend:** Streamlit chat application
- **Backend:** FastAPI service
- **Settlement asset:** Testnet USDC
- **Network:** Base Sepolia
- **Agent infrastructure:** One LangChain broker agent using GPT-5.4 mini and tools
- **Payments:** Circle Agent Wallet and x402 nanopayments
- **Onchain component:** Minimal insurance-manager smart contract
- **Important limitation:** This is a testnet demonstration, not legally valid insurance

## Technology Stack

| Layer | Choice | MVP responsibility |
|---|---|---|
| Frontend | Streamlit | Chat, budget approval, recommendation review, policy status, and payment receipt |
| Backend | FastAPI | Agent endpoint, validation, mocked knowledge service, policy actions, and demo-oracle endpoint |
| Agent framework | LangChain 1.x `create_agent` | One GPT-5.4 mini broker with a small fixed tool set and structured responses |
| Data validation | Pydantic | Validate trip details, policy recommendations, money amounts, and tool results |
| Agent wallet | Circle Agent Wallet | Broker balance checks, controlled USDC spending, x402 payment, and payment receipts |
| Blockchain | Base Sepolia | Test-USDC escrow, policy records, refunds, and claim payouts |
| Smart contract | Solidity insurance manager | Deterministic custody, policy state transitions, and payout rules |
| Mock services | FastAPI routes | Insurance knowledge catalogue, underwriting rules, and flight-oracle input |

The application uses the locally installed `.agents/skills/` LangChain guidance during development. The most relevant skills are:

- `ecosystem-primer`
- `langchain-dependencies`
- `langchain-fundamentals`
- `langchain-middleware`

These skills guide the coding agents building CoverPilot; they are not runtime tools exposed to the customer-facing broker. At runtime, the broker receives only explicitly implemented and validated Python tools from the FastAPI application.

### Why LangChain instead of LangGraph or Deep Agents

CoverPilot has one fixed-purpose agent with a small tool set, so LangChain `create_agent` is the simplest fit for the MVP. Budget limits, purchase approval, contract writes, and claim resolution remain deterministic application or smart-contract operations rather than model-controlled workflow steps.

LangGraph persistence and interrupt/resume flows would become useful if a later version must recover long-running policy workflows across sessions. Deep Agents would add planning, filesystem, memory, and subagent capabilities that this narrow broker does not need.

## Component Flow

```text
Traveler
   |
   v
Streamlit chat and policy UI
   |
   v
FastAPI application
   |
   +--> LangChain broker agent (GPT-5.4 mini)
   |       |
   |       +--> validated broker tools
   |               +--> Circle Agent Wallet and x402
   |               +--> mocked insurance knowledge service
   |               +--> Base Sepolia insurance manager
   |
   +--> privileged mock-oracle endpoint --> Base Sepolia insurance manager
```

Streamlit owns presentation and conversational session state. FastAPI owns authentication boundaries, validation, idempotency, agent execution, and service integration. The smart contract owns funds and final policy state. The language model never directly constructs arbitrary transactions or decides whether a claim is valid.

## Product Definition

CoverPilot is a conversational travel-insurance broker powered by one AI agent and a Circle Agent Wallet.

The customer does not need to know which insurance product they want. They describe their trip, concerns, and maximum budget naturally:

> “I am traveling to a distant country on a long flight. Please help make my trip safer. My maximum budget is €100.”

The broker agent asks follow-up questions, understands the trip, pays a specialist knowledge service for a recommendation, and presents one suitable flight-delay policy within the approved budget.

### Core promise

> **Describe the safety you want, not the insurance product. The agent finds, explains, and purchases suitable protection within your budget.**

The MVP supports only flight-delay insurance. Health, home, and broader travel insurance are future extensions rather than working hackathon features.

## Customer Experience

The chat-first application allows the traveler to:

- Describe their trip naturally
- Answer follow-up questions
- Set and approve a maximum budget
- Authorize a limited paid insurance search
- Review one personalized recommendation
- Accept or reject the policy
- View a simple budget summary and policy status
- Receive an automatic payout if the covered delay occurs

The customer-facing experience does not mention liquidity-pool selection or other crypto implementation details.

## End-to-End Flow

### 1. Conversational discovery

The traveler describes the trip and desired feeling of safety. The broker agent asks only for information needed to find coverage, such as:

- Destination and travel dates
- Flight number or route
- Number of travelers
- Main concerns
- Maximum budget

The agent summarizes the request before any funds are committed.

### 2. Budget authorization

The customer is shown a clear authorization message:

> “I can search for suitable protection within your 100 USDC budget. This search may cost up to 5 USDC, even if you do not purchase the recommended policy.”

The customer signs a transaction transferring the approved maximum USDC budget into the Budget Escrow. The agent cannot spend more than the approved amount.

If the customer entered the budget in euros, the interface shows the simulated USDC equivalent before authorization.

### 3. Paid insurance search

The smart contract releases a dynamic research allowance equal to 1–5% of the maximum budget. The broker's Circle Agent Wallet uses that allowance to pay the mocked insurance knowledge service through x402.

The payment is real on testnet and produces a receipt. The service logic and insurance catalogue are mocked.

### 4. Policy recommendation

After payment, the knowledge service returns one policy containing:

- Policy name
- Premium
- Fixed payout
- Delay trigger
- Coverage period
- Internal risk tier
- Internal liquidity-pool identifier
- Human-readable recommendation reason

The agent does not invent premiums, calculate risk, or create policy terms. It explains the structured response from the knowledge service in plain language.

### 5. Customer decision

The agent shows only customer-relevant terms:

- Recommendation
- Price
- Fixed payout
- Delay trigger
- Coverage dates
- Important exclusions included in the mocked template

It does not explain which P2P liquidity pool was selected.

#### If the customer rejects the policy

- The x402 research fee remains paid.
- The unused budget is unlocked and returned.
- The customer receives a payment receipt.

#### If the customer accepts the policy

- The x402 research fee remains paid.
- The premium enters the mocked Policy Vault.
- The remaining unused budget is unlocked and returned.
- An onchain policy record is created.

### 6. Policy lifecycle

The policy is assigned internally to a mocked low-, medium-, or high-risk P2P liquidity pool.

- The premium remains in the Policy Vault until the trip is resolved.
- Simulated yield accrues for the customer.
- The selected pool reserves mocked liquidity for the possible payout.
- Pool selection and LP mechanics are hidden from the normal customer interface.

### 7. Claim resolution

A mocked flight oracle submits the flight result.

- **No qualifying delay:** The premium principal goes to the selected LP pool, and simulated yield is returned to the customer.
- **Qualifying delay:** The selected LP pool pays the fixed test-USDC benefit automatically. The premium remains earned by the pool, and simulated yield is returned to the customer.

The policy ends in either `EXPIRED` or `PAID_OUT` state.

## Example Financial Flow

The traveler authorizes a maximum budget of **100 USDC**.

| Event | Amount |
|---|---:|
| Maximum budget locked | 100 USDC |
| x402 insurance-search fee | −3 USDC |
| Accepted policy premium | −42 USDC |
| Unused budget returned | +55 USDC |
| Simulated yield returned after resolution | +0.20 USDC |
| Claim payout if delay trigger is met | +300 USDC |

If the traveler rejects the recommendation, only the 3 USDC research fee is deducted and 97 USDC is returned.

## One LangChain Broker Agent

The application uses one LangChain `create_agent` broker rather than separate interview, research, wallet, and policy agents.

GPT-5.4 mini handles:

- Conversational trip discovery
- Follow-up questions for missing information
- Trip and budget confirmation
- Knowledge-service request construction
- Tool selection and execution
- Recommendation explanation
- Customer-friendly policy summary
- Policy and payment-status queries

### Agent tools

The broker receives a small, explicit set of FastAPI-backed Python tools:

- `get_wallet_balance()`
- `prepare_budget_authorization(max_budget_usdc)`
- `get_research_allowance(policy_draft_id)`
- `pay_knowledge_service(policy_draft_id)`
- `get_policy_recommendation(policy_draft_id, trip_details)`
- `purchase_policy(policy_draft_id)`
- `reject_policy(policy_draft_id)`
- `get_policy_status(policy_id)`

Tool inputs and outputs use Pydantic schemas. FastAPI checks authorization, amount limits, current policy state, duplicate requests, and contract results before returning data to the model. The model may choose an appropriate tool and explain its result, but it cannot override these checks.

The broker agent cannot submit flight results or trigger claims. The mocked oracle is a separate privileged component so that the agent recommending a policy cannot approve its own payout.

## Circle Agent Wallet

The Circle Agent Wallet is a meaningful part of the broker's work. It is used to:

- Hold the broker's payment identity
- Check balances
- Respect the customer-authorized research allowance
- Pay the knowledge service through x402
- Capture the payment receipt or transaction reference
- Explain what data was purchased and why

The workflow satisfies the Circle challenge requirement to go beyond a single USDC transfer by making the wallet part of a repeatable agent task.

Circle Agent Wallet provides wallets, spending controls, USDC payments, Gateway, and x402 nanopayments. No documented Circle Agent Stack product is being represented as a yield vault.

### Alignment with the Circle Agent Wallet brief

- The agent performs meaningful wallet actions: balance checks and a paid x402 service request.
- The wallet operates inside a customer-authorized research allowance.
- The payment buys a specific insurance recommendation and produces a receipt or transaction reference.
- The UI explains what the agent purchased, why it purchased it, and how much it spent.
- The same wallet-as-a-job workflow can be repeated for another traveler.
- The implementation should begin from Circle's LangChain-compatible Agent Stack starter material described in `Circle Agent Wallet.pdf` rather than creating an unrelated wallet abstraction.

## Mocked x402 Knowledge Service

The middleware exposes a paid endpoint such as:

```text
POST /insurance/recommend
Price: dynamic, 1–5% of the approved customer budget
```

The endpoint is protected by x402. After payment, it evaluates mocked rules and returns a predefined policy template.

Example response:

```json
{
  "policyName": "Long-Haul Delay Protect",
  "premiumUsdc": 42,
  "payoutUsdc": 300,
  "delayTriggerMinutes": 180,
  "coverageStart": "2026-06-28T08:00:00Z",
  "coverageEnd": "2026-06-29T08:00:00Z",
  "riskTier": "LOW",
  "poolId": "POOL-LOW-01",
  "reason": "Long-haul flight with limited connection tolerance"
}
```

The knowledge service represents a future catalogue of insurance templates and underwriting knowledge. Its data, premiums, risk scoring, and recommendation rules are mocked for the hackathon.

## FastAPI Boundary

The MVP can be implemented with a small API surface:

| Endpoint | Purpose |
|---|---|
| `POST /chat` | Run one conversational turn and return agent messages or an approval request |
| `POST /budget/authorize` | Validate the approved cap and prepare or record the escrow transaction |
| `POST /insurance/recommend` | x402-protected mocked knowledge-service response |
| `POST /policy/purchase` | Validate approval and submit the policy purchase |
| `POST /policy/reject` | Deduct the paid research fee and unlock the remaining budget |
| `GET /policy/{policy_id}` | Return policy, payment, and claim status for the UI |
| `POST /oracle/resolve` | Privileged demo-only flight result submission |

For the hackathon, these routes may live in one FastAPI project while preserving logical boundaries between the broker API, paid knowledge service, and privileged oracle. Money-changing routes require idempotency keys so a Streamlit rerun or repeated agent tool call cannot duplicate a payment or contract write.

### Responsibility boundary

- **GPT-5.4 mini:** asks questions, normalizes the trip request, chooses approved tools, and explains verified results.
- **LangChain:** binds the tool set, manages the agent turn, and returns structured output.
- **FastAPI:** validates schemas and permissions, calculates the 1–5% research fee from deterministic mocked rules, enforces idempotency, and coordinates integrations.
- **Circle Agent Wallet:** pays the x402-protected service and returns payment evidence.
- **Smart contract:** escrows USDC and enforces policy, refund, and payout state transitions.
- **Mock oracle:** submits flight outcomes through a privileged route; it is not an agent tool.

## Onchain Insurance Manager

The Onchain Insurance Manager is a minimal smart contract deployed on Base Sepolia.

It combines the hackathon's essential onchain responsibilities:

- Budget escrow
- Policy registry
- Mock policy vault
- Mock pool accounting
- Policy-state transitions
- Claim-trigger evaluation
- Test-USDC refunds and payouts

### Onchain records

The contract records:

- Customer wallet address
- Locked maximum budget
- Research allowance and paid fee
- Premium
- Fixed payout
- Delay threshold
- Policy start and end times
- Hashed flight identifier
- Hashed recommendation or API response
- x402 payment reference
- Internal risk tier and pool ID
- Policy status
- Oracle result
- Refund or payout transaction

### Offchain information

The following remains offchain:

- Customer name and identity
- Passport or booking information
- Full conversation history
- Raw knowledge-service response
- Other unnecessary personal travel information

Hashes can be stored onchain to prove that offchain records were not changed after the policy was created.

## Mocked Policy Vault and P2P Pools

The system models three P2P liquidity pools:

| Pool | Insurance risk | Simulated LP return |
|---|---|---|
| Low-risk pool | Lower expected claim probability | Lower return |
| Medium-risk pool | Moderate expected claim probability | Medium return |
| High-risk pool | Higher expected claim probability | Higher return |

The knowledge service selects the pool as part of its mocked underwriting response. The customer does not select or see the pool.

The pool economics, LP deposits, capital requirements, and yield calculations are mocked. For demonstration purposes, a funded testnet pool wallet may still execute a real test-USDC claim payout.

## Mock Flight Oracle

A privileged admin or demo endpoint submits:

- Hashed flight identifier
- Arrival status
- Delay duration
- Observation timestamp

The smart contract compares the submitted delay with the policy trigger and releases the payout when the condition is met.

The external flight-data source and oracle network are mocked. The separation between the broker agent and oracle is real in the application architecture.

## Customer Receipt

The customer-facing term is **Budget Summary** or **Payment Receipt**, not “complete spending ledger.”

It shows:

- Maximum budget authorized
- Insurance-search fee paid
- Policy premium, if purchased
- Unused amount returned
- Simulated yield returned
- Claim payout, if triggered

Transaction hashes and raw onchain details are available only in an optional technical-details view. This preserves a non-crypto-native experience while satisfying the hackathon requirement for receipts and payment logs.

## Real vs. Mocked

### Real

- Conversational AI experience
- One tool-using broker agent
- Circle Agent Wallet
- x402 knowledge-service payment
- Testnet USDC movements
- Base Sepolia smart contract
- Onchain policy record
- Customer budget receipt
- Automatic claim transaction after oracle submission

### Mocked

- Insurance catalogue
- Underwriting and premium calculation
- Risk scoring and pool selection
- P2P pool economics
- LP deposits and returns
- Policy-vault yield
- Flight-data source and oracle network
- Regulated underwriting and compliance
- Legally binding policy issuance

## Legal and Product Disclaimer

Real insurance must normally be issued by an authorized insurer and comply with applicable insurance, consumer-protection, privacy, and financial regulations. CoverPilot does not provide legally valid coverage.

The interface must display:

> **Demo policy using testnet funds. This is not real insurance coverage.**

## Demo Story

1. A traveler asks for help making a long-distance trip safer with a 100 USDC budget.
2. The broker asks conversational follow-up questions.
3. The traveler approves the budget and maximum research fee.
4. The broker's Circle Agent Wallet pays the knowledge service through x402.
5. The UI displays the x402 receipt and explains why the data was purchased.
6. The broker presents one flight-delay recommendation.
7. The traveler purchases the policy.
8. The smart contract returns the unused budget and records the policy.
9. The demo oracle submits a delay longer than the policy trigger.
10. The selected mocked pool sends a real test-USDC payout.
11. The traveler sees the updated policy status and simple budget summary.

## Final Decision

Build **CoverPilot** as a narrow, conversational flight-delay insurance demonstration.

The strongest hackathon story is not merely “insurance onchain.” It is that one AI broker manages a customer-approved budget, purchases specialist insurance knowledge through x402, recommends suitable protection, creates an auditable onchain policy, and completes an automatic test-USDC claim workflow.
