# Hackathon Brief Research Notes

_Date researched: 2026-06-19_
_Source file reviewed: `Hackathon-brief.md`_

## 1) Executive summary

`Hackathon-brief.md` describes the **AI Agents Hackathon** in Berlin as a builder-focused event under the broader **AI Agents Summit 2026** umbrella.

From the brief plus linked/official sources, the event appears to be positioned around:
- production-grade AI agents
- on-chain commerce and finance
- agent infrastructure
- practical, demoable projects rather than prototype-only experiments

### Important consistency note
There is a **date/duration discrepancy across sources**:
- `Hackathon-brief.md` says **June 19–20, 2026** and reads like a **2-day / ~48-hour** event.
- The official summit site says the hackathon runs **Friday, June 19 through Sunday, June 21, 2026** and explicitly calls it a **72-hour build sprint**.
- Berlin Blockchain Week’s event map also lists **June 19–21, 2026**.

This should be treated as a planning risk until the organizers confirm the final schedule.

---

## 2) What `Hackathon-brief.md` says

### Core event details from the brief
- **Name:** AI Agents Hackathon
- **Theme:** “Build Tomorrow's On-Chain Agent Economy”
- **Dates in brief:** June 19–20, 2026
- **Time shown in brief:** 6:00 PM to 10:00 PM
- **Location:** Berlin, Germany
- **Venue:** 42berlin
- **Organizer context:** part of **AI Agents Summit 2026**

### Focus areas named in the brief
- **Agentic commerce**: payments, x402, automation, subscriptions
- **Agent infrastructure**: APIs, ERC-8004, identity, verifiable logs, monitoring, reputation

### Prize information in the brief
- **$4,000+ total prize pool**
- Mentioned sponsors/partners for prizes:
  - Circle
  - Tavily
  - Nebius / TokenFactory
  - OOBE Protocol / Synapse RPC
  - Blockchain for Good
- Additional support mentioned:
  - Nebius credits
  - Softstack deals platform + consulting for top teams post-hackathon

### Rules/requirements in the brief
- Team size: **1–5**
- Remote participation: **partially allowed**, but **at least one team member must be onsite** and present the final pitch
- AI usage: **allowed and encouraged**
- Projects must start from an **empty repo during the hackathon**
- Judging criteria include technical sophistication, creativity, usability, value proposition, ecosystem impact

### Agenda from the brief
- **Fri 19 June, 6PM**: opening ceremony, challenge briefs, team formation, kickoff
- **Workshops by Circle & Cloudflare**
- **Sat 20 June**: workshops, mentor sessions, office hours
- **3:30 PM**: project submission
- **4:30 PM**: pitches, live demos, judging
- **8:30 PM**: winner announcements + networking
- Venue stays open overnight

---

## 3) URL-by-URL findings

Below is what I found by checking the URLs embedded in `Hackathon-brief.md`.

### 3.1 Circle
- **URL:** https://www.circle.com/?utm_source=luma
- **HTTP check:** reachable
- **Page title:** _Circle | The full-stack platform for the internet financial system_
- **What it is:** Circle presents itself as infrastructure for the “internet financial system,” centered around on-chain payments and stablecoin-based financial rails.
- **Relevant details found:**
  - promotes **USDC**, **Circle Payments Network (CPN)**, and developer/financial infrastructure
  - homepage messaging explicitly references the **agentic economy**
  - positioning is highly aligned with the hackathon’s agentic commerce theme
- **Why it matters for the hackathon:** strong fit for payment-enabled agents, settlement, monetization, and on-chain commerce flows
- **Source:** https://www.circle.com/

### 3.2 Tavily
- **URL:** https://www.tavily.com/?utm_source=luma
- **HTTP check:** reachable
- **Page title:** _Tavily_
- **What it is:** Tavily describes itself as a **real-time search engine / API for AI agents and RAG workflows**.
- **Relevant details found:**
  - positioned as web search + content extraction for agent workflows
  - docs and product pages emphasize live web access for AI systems
  - direct relevance for research agents, browsing agents, and retrieval-heavy hacks
- **Why it matters for the hackathon:** useful for agents that need web search, research, citations, monitoring, or external information gathering
- **Sources:**
  - https://www.tavily.com/
  - https://docs.tavily.com/welcome

### 3.3 Nebius
- **URL:** https://nebius.com/?utm_source=luma
- **HTTP check:** reachable
- **Page title:** _The Ultimate AI Cloud_
- **What it is:** Nebius markets a purpose-built **AI cloud** for training and inference.
- **Relevant details found:**
  - homepage emphasizes full-stack AI cloud infrastructure
  - inference page emphasizes production inference, hardware-to-token-cost optimization, and “managed inference with Token Factory”
  - clearly relevant for teams needing hosted inference infrastructure
- **Why it matters for the hackathon:** supports the infrastructure side of building production-grade agents; prize references also point to **TokenFactory** and model credits
- **Sources:**
  - https://nebius.com/
  - https://nebius.com/solutions/inference
  - https://nebius.com/ai-cloud

### 3.4 Nebius Inference / TokenFactory link
- **URL:** https://nebius.com/solutions/inference?utm_source=luma
- **HTTP check:** reachable
- **Page title:** _AI Model Inference on Nebius — Managed and Custom Inference Infrastructure_
- **What it adds beyond the main site:**
  - focused specifically on production inference
  - highlights cost/performance optimization
  - mentions **managed inference with Token Factory**
- **Hackathon relevance:** likely intended for teams shipping model-backed agents that need scalable inference rather than just demos
- **Source:** https://nebius.com/solutions/inference

### 3.5 OOBE Protocol
- **URL:** https://www.oobeprotocol.ai/?utm_source=luma
- **HTTP check:** reachable
- **Page title:** _OOBE Protocol - Build AI Agents on Solana_
- **What it is:** OOBE positions itself as an all-in-one platform to create, run, and scale autonomous AI agents on **Solana**.
- **Relevant details found:**
  - focuses on agent creation, execution, and on-chain actions
  - emphasizes Solana-native agent workflows
  - strong fit with the “on-chain agent economy” framing
- **Why it matters for the hackathon:** directly relevant to builders who want agents with blockchain-native identity, execution, monetization, or coordination
- **Source:** https://www.oobeprotocol.ai/

### 3.6 Synapse by OOBE Protocol
- **URL:** https://synapse.oobeprotocol.ai/?utm_source=luma
- **HTTP check:** reachable
- **Page title:** _Synapse_
- **What it is:** Synapse is presented as a **gateway / RPC layer** for Solana.
- **Relevant details found:**
  - marketed as low-latency Solana infrastructure
  - page highlights **99.99% uptime SLA**, **<50ms average latency**, and **24/7 support**
  - specifically targets developers and agents needing high-performance RPC
- **Why it matters for the hackathon:** practical infra for teams building real-time, chain-aware agents on Solana
- **Source:** https://synapse.oobeprotocol.ai/

### 3.7 OOBE PDF guidelines / side-track proposal
- **URL:** https://drive.google.com/file/d/19O0_qYmrDzWv8GxZm3GylvzsVw3zclup/view?usp=drive_link&utm_source=luma
- **HTTP check:** reachable
- **Document title:** _OOBE_Berlin_On_Chain_Agent_Side Track.pdf_
- **What I extracted from the PDF:**
  - OOBE proposes a dedicated **“On-Chain Agent Track”**
  - stated goal: build useful AI agents that create **measurable on-chain activity**
  - expected stack usage includes:
    - **Synapse Agent Protocol**
    - **Synapse RPC**
    - **SAP escrow** as an obligatory part of the flow
  - submission expectations include:
    - 1 SAP agent registered
    - escrow included
    - 25+ agent calls during the hackathon
    - 25+ SAP-related interactions
    - working UI/API/CLI/bot
    - public GitHub repo
    - explanatory video or X thread
  - prize structure in the PDF:
    - **1st:** $500 + 2 months Synapse RPC Advanced
    - **2nd:** $300 + 1 month Synapse RPC Advanced or 3 months Starter
    - **3rd:** $200 + 2 months Starter
- **Why it matters:** this is much more specific than the brief and is likely the real operational guide for the OOBE side track
- **Source:** Google Drive PDF linked from the brief

### 3.8 Blockchain for Good Alliance
- **URL:** https://chainforgood.org/?utm_source=luma
- **HTTP check:** reachable
- **Page title:** _Blockchain for Good_
- **What it is:** a blockchain-for-social-impact alliance / ecosystem.
- **Relevant details found:**
  - mission centers on applying blockchain to societal challenges
  - public FAQ mentions grants/partnerships for projects with social-good alignment
  - the brief’s **$500 best social impact** bonus is consistent with this positioning
- **Why it matters for the hackathon:** relevant if a team wants to target the bonus prize for social impact
- **Source:** https://chainforgood.org/

---

## 4) Supplemental web search findings

These were not all directly stated in `Hackathon-brief.md`, but they came up in official or near-official event sources.

### 4.1 Official Luma event page confirms the brief’s framing
- **Source:** https://luma.com/ai-agents-hackathon-2026
- The Luma page matches the brief’s title and general positioning.
- It repeats the Berlin / 42berlin framing and the hackathon’s focus on agentic commerce and infrastructure.

### 4.2 AI Agents Summit site expands the event into a larger 4-day program
- **Source:** https://ai-agents-summit.com/
- The summit site says **AI Agents Summit 2026** runs **June 18–21, 2026** in Berlin.
- It separates the event into:
  - **June 18:** summit day / talks / demos at **Spielfeld Digital Hub**
  - **June 19–21:** hackathon at **42Berlin**
- It explicitly calls the hackathon a **72-hour build sprint**.

### 4.3 Summit FAQ adds more detail than the brief
- **Source:** https://ai-agents-summit.com/
- The FAQ says the hackathon is open to **developers, designers, domain experts, and founders**.
- It says **solo participants are welcome** and **team formation happens on Day 1**.
- It names **four tracks**:
  - Agentic Commerce
  - Agentic Finance
  - Personal Assistant
  - Agent Infrastructure

### 4.4 Track discrepancy vs brief
- **Brief:** mostly emphasizes **2 tracks**
  - Agentic commerce
  - Agent infrastructure
- **Summit FAQ:** names **4 tracks**
  - Agentic Commerce
  - Agentic Finance
  - Personal Assistant
  - Agent Infrastructure

This suggests either:
1. the brief is abbreviated, or
2. the track structure changed over time.

### 4.5 Berlin Blockchain Week listing supports the longer date window
- **Source:** https://berlinblockchainevents.com/
- The Berlin Blockchain Week map lists **AI Agents Summit 2026** for **June 18–21**.
- It places the event inside the broader Berlin Blockchain Week calendar.
- This reinforces that the hackathon is likely being promoted as part of a larger multi-day ecosystem event.

### 4.6 AI Agents Berlin community context
- **Source:** https://aiagentsberlin.xyz/
- AI Agents Berlin presents itself as Berlin’s leading community around **agentic AI**, autonomous systems, and the future of digital economies.
- The summit FAQ also attributes the event to AI Agents Berlin / Raphael Gutsche.
- This makes the hackathon look community-anchored rather than a one-off standalone contest.

### 4.7 42 Berlin venue fit
- **Source:** https://42berlin.de/
- 42 Berlin is a **tuition-free, peer-to-peer coding school** in Berlin.
- Its official messaging emphasizes 24/7 campus access and project-based learning, which fits the hackathon’s overnight-building framing.

### 4.8 Cloudflare workshop relevance
- **Sources:**
  - https://developers.cloudflare.com/workers-ai/
  - https://www.cloudflare.com/products/workers-ai/
- The brief mentions workshops by **Circle & Cloudflare**.
- Cloudflare’s current AI platform positioning is centered on **Workers AI**, serverless AI inference, and globally distributed app execution.
- For builders, that suggests likely relevance for agent hosting, inference, edge execution, APIs, or web-integrated toolchains.

### 4.9 Softstack support mention
- **Source:** https://softstack.io/
- Softstack positions itself as a Web3 software development / cybersecurity / consulting partner.
- The brief’s note about post-hackathon access to Softstack’s deals platform and consulting appears consistent with that service positioning.

### 4.10 Algorand mention in the brief
- The brief says AI usage is allowed and encouraged and that **Algorand AI tooling and templates** will be provided.
- I did not find a single official page directly confirming this exact hackathon-specific tooling promise, but Algorand’s official ecosystem/docs pages do show an active builder and standards environment.
- This line should be treated as **brief-sourced unless organizers provide a direct tooling link**.

---

## 5) Cross-source observations

### Clear strengths of the event
- Strong alignment between sponsor stack and hackathon theme:
  - **Circle** -> payments / stablecoins / agentic commerce
  - **Tavily** -> web search / retrieval for agents
  - **Nebius** -> inference / AI compute
  - **OOBE / Synapse** -> on-chain agent rails on Solana
  - **Blockchain for Good** -> impact-oriented bonus category
- Venue and summit context make it look like a serious builder event rather than a casual meetup.
- Overnight access and infra-heavy sponsors suggest emphasis on **shipping** rather than only pitching.

### Main ambiguities / risks to clarify
1. **Is the hackathon 2 days or 3 days?**
   - Brief says June 19–20.
   - Summit site + event ecosystem pages say June 19–21.
2. **Are there 2 tracks or 4 tracks?**
   - Brief foregrounds 2.
   - Summit FAQ lists 4.
3. **What does “6:00 PM to 10:00 PM” actually mean?**
   - It cannot represent the full hackathon duration if the event includes overnight hacking and next-day demos.
   - It may only describe the kickoff window or venue schedule slice.
4. **Where are the official rules/guidelines besides the OOBE side-track PDF?**
   - The Google Drive doc is clearly OOBE-specific, not necessarily the universal hackathon rulebook.
5. **What are the exact submission mechanics?**
   - The brief mentions submission time and pitch time but not the submission platform or required deliverables across all tracks.

---

## 6) Practical takeaways for a participant/team

Based on the brief plus the linked sources, the strongest likely project profiles are:
- an agent with a **real payment / settlement flow**
- a **web-aware agent** using external search/retrieval
- a **Solana-connected agent** with verifiable on-chain actions
- an infra/tooling project that demonstrates monitoring, logs, identity, or execution reliability
- a project with measurable real usage rather than only a concept demo

For prize targeting:
- **Circle** likely rewards payment/commerce usefulness
- **Tavily** likely rewards research/web-enabled agent behavior
- **Nebius** likely rewards strong use of model infra / inference stack
- **OOBE** likely rewards real on-chain interaction with their rails, especially if the PDF side-track applies
- **Blockchain for Good** likely rewards clear social-impact framing

---

## 7) Source list

### File reviewed
- `Hackathon-brief.md`

### URLs embedded in the brief
- https://www.circle.com/?utm_source=luma
- https://www.tavily.com/?utm_source=luma
- https://nebius.com/?utm_source=luma
- https://nebius.com/solutions/inference?utm_source=luma
- https://www.oobeprotocol.ai/?utm_source=luma
- https://synapse.oobeprotocol.ai/?utm_source=luma
- https://drive.google.com/file/d/19O0_qYmrDzWv8GxZm3GylvzsVw3zclup/view?usp=drive_link&utm_source=luma
- https://chainforgood.org/?utm_source=luma

### Additional sources checked
- https://luma.com/ai-agents-hackathon-2026
- https://luma.com/ai-agents-summit-2026
- https://ai-agents-summit.com/
- https://berlinblockchainevents.com/
- https://42berlin.de/
- https://aiagentsberlin.xyz/
- https://docs.tavily.com/welcome
- https://developers.cloudflare.com/workers-ai/
- https://www.cloudflare.com/products/workers-ai/
- https://softstack.io/

---

## 8) Recommended next checks

If you want the brief turned into a sharper participant-ready memo, the next things worth verifying are:
1. final official hackathon duration (**June 19–20 vs June 19–21**)
2. final track list (**2 vs 4 tracks**)
3. submission platform / deliverables
4. whether the OOBE PDF is an official public side-track rulebook or just a sponsor proposal
5. whether there are direct sponsor-specific APIs, credits, templates, or coupon codes available before kickoff
