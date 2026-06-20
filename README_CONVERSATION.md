# CoverPilot — conversational broker (LangChain)

This folder contains a **minimal conversational AI slice** of CoverPilot: one **LangChain 1.x** broker agent (`create_agent`) with a **fixed tool set** and an **in-memory mock** for wallet / x402 / policy transitions. Use it to iterate on prompts and tool boundaries before wiring **FastAPI + Circle + Base**.

## Voice later?

Yes. **Chat-first, voice-second** is a good pattern:

- Keep **one agent backend** (this module / later your FastAPI `/chat` handler).
- Add a **speech layer** in front: **STT** (e.g. Whisper-style streaming) → text → same `agent.invoke` → **TTS** on the assistant reply.
- Voice adds **latency, barge-in, and turn-detection** UX work; it does not replace the need for **structured tools** and **server-side validation** (your `ideas.md` already separates broker from oracle).

Technically you will still have: **LLM + tools + checkpointer**; voice is I/O only.

## What was implemented (technical breakdown)

| Piece | Role |
|--------|------|
| **`create_agent`** | LangChain 1 recommended agent loop (LangGraph-backed runtime). See `.agents/skills/langchain-fundamentals/SKILL.md`. |
| **`ChatOpenAI`** | Model implementation; API key from `OPENAI_API_KEY`. Model id from `COVERPILOT_CHAT_MODEL` (default `gpt-4o-mini`). |
| **`@tool` functions** | Small, explicit surface the model may call; **all money/policy rules** stay in `mock_backend.py`. |
| **`MemorySaver` + `thread_id`** | Conversation memory across Streamlit turns, per `.agents/skills/langchain-fundamentals` (checkpointer + `configurable.thread_id`). |
| **`recursion_limit`** | Caps agent steps per invoke (same skill). Override with `COVERPILOT_RECURSION_LIMIT`. |
| **`streamlit_app.py`** | Minimal UI: one thread per session, sidebar reset, debug JSON for mock state. |

**Not** included yet (by design): Human-in-the-loop middleware for spend approvals (`HumanInTheLoopMiddleware` from `.agents/skills/langchain-middleware/SKILL.md`), LangSmith-only streaming UI, FastAPI, Circle, x402 HTTP, contracts.

## Setup

```bash
cd ai-agents-hackathon
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-conversation.txt
cp .env.example .env   # then put OPENAI_API_KEY in .env or export in shell
```

Optional observability (recommended in skills — `.agents/skills/ecosystem-primer/SKILL.md`):

```bash
export LANGSMITH_TRACING=true
export LANGSMITH_API_KEY=...
export LANGSMITH_PROJECT=coverpilot-conversation
```

## Run Streamlit

```bash
cd ai-agents-hackathon
source .venv/bin/activate
export OPENAI_API_KEY=sk-...
streamlit run streamlit_app.py
```

Try a prompt like: *“I fly BER→SFO June 28, return June 29, one traveler, worried about long delays. Max 100 USDC.”* Then follow the agent through **prepare → confirm → pay → recommend → purchase**.

## Project layout

```text
ai-agents-hackathon/
  coverpilot_conversation/
    agent.py                 # build_broker_agent()
    tools.py                 # LangChain tools (mock + CRM lookup)
    mock_backend.py          # deterministic demo state + session_customer_id
    customer_directory.py    # recurring profiles (demo: Vasiliy)
    prompts.py               # Betty / TrustLayer broker instructions
  streamlit_app.py           # minimal tester UI + CRM session id sidebar
  requirements-conversation.txt
  .env.example
```

## Recurring customer (demo CRM)

`lookup_customer_profile` resolves **TrustLayer** “known travelers”. The Streamlit sidebar **CRM session customer id** defaults to `vasiliy`; when the model calls `lookup_customer_profile("")`, that id is used—so Betty can greet **Vasiliy** by name and suggest the usual **~40 USDC** delay budget before asking for trip details.

## Skills consulted (source of truth for patterns)

Development-time guidance (not loaded at runtime by the app):

- `.agents/skills/ecosystem-primer/SKILL.md` — why **LangChain** (single-purpose agent) vs LangGraph / Deep Agents.
- `.agents/skills/langchain-dependencies/SKILL.md` — versions and installs (`requirements-conversation.txt`).
- `.agents/skills/langchain-fundamentals/SKILL.md` — `create_agent`, `@tool`, `MemorySaver`, `recursion_limit`.
- `.agents/skills/langchain-middleware/SKILL.md` — when you add **HITL** around `purchase_policy` / `pay_knowledge_service` for production.

## Next integration steps (toward full CoverPilot)

1. Move `build_broker_tools` implementations from `MockBrokerBackend` to **FastAPI** routes that validate Pydantic schemas, idempotency keys, and call **Circle + x402 + contract**.
2. Keep **the same tool names and JSON shapes** so the broker prompt stays stable.
3. Add **HITL** or a dedicated **UI approval step** for budget lock and purchase, aligned with `langchain-middleware` (requires checkpointer + `Command` resume if using LangChain HITL in-process).
