# AG-UI Account Opening POC

A vertical slice for an Angular + AG-UI + FastAPI + LangGraph account-opening experience.

## What this POC demonstrates
1. RM submits a natural-language account-opening request.
2. FastAPI exposes a LangGraph workflow through the AG-UI protocol.
3. The graph retrieves a **mock** client profile and checks required fields deterministically.
4. The graph publishes typed UI state for Angular to render through a controlled widget registry.
5. Angular renders a joint-owner form and application summary from metadata.
6. LangGraph pauses at an explicit human approval interrupt.
7. While paused, the RM can request field changes conversationally; the graph applies extracted updates, revalidates requirements and presents a new summary.
8. Every revised summary requires a fresh explicit approval.
9. Only an approved review reaches mock draft creation.

No real account is opened and no production system is called.

## Architecture
```text
Angular UI -> AG-UI adapter (fetch + SSE) -> FastAPI /agent
  -> ag-ui-langgraph -> LangGraph
       -> request understanding (LLM slot extraction)
       -> mock client profile -> deterministic requirements
       -> Angular form / summary UI state
       -> interrupt() waits for human action
            | EDIT -> extract changes -> revalidate -> new summary -> interrupt()
            | APPROVE -> mock draft creation
            | REJECT -> finish without draft
```

## Prerequisites
- Python 3.12 (also compatible with 3.11)
- Node.js 20+
- Angular CLI matching your application version

## Run backend
```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Set OPENAI_API_KEY in .env; never commit .env
uvicorn main:app --reload --port 8000
```
Health: http://localhost:8000/health  
AG-UI endpoint: `POST http://localhost:8000/agent`

## Internal model endpoint
The POC uses `langchain-openai` against an OpenAI-compatible internal endpoint. Configure `OPENAI_BASE_URL`, `OPENAI_MODEL`, and `OPENAI_API_KEY` in `backend/.env`. Set `INTERNAL_CA_CERT` to your organization's CA certificate path if required. TLS verification remains enabled.

Set `LLM_ENABLED=false` to test the protocol using deterministic regex fallback without calling the model. The model is used only for intent/slot extraction; it does not decide KYC eligibility, business validation, authorization, suitability, or transaction approval.

## Conversational review and HITL
- When required fields are complete, the graph sets `approval_status=PENDING` and renders the application summary.
- The `await_human_approval` node calls LangGraph `interrupt()`; no draft-creation side effect occurs before the pause.
- The review interrupt supports three explicit actions:
  - `APPROVE`: resume and create the mock draft.
  - `REJECT`: resume and finish without a draft.
  - `EDIT`: resume with a natural-language change request, extract only non-empty fields, update the checkpointed state, re-run client lookup and deterministic requirement checks, then render a new summary.
- Every edited summary increments `reviewVersion` and requires a new approval interrupt. Previous approval does not carry forward.
- Angular resumes the same `threadId` with the interrupt ID and structured payload. The LLM does not decide approval.

The approval payload is a POC interaction contract, not a production authorization mechanism. In production, bind the decision to an authenticated RM identity, application version/hash, entitlements, audit event and server-side approval policy. Never treat a browser-supplied boolean as sufficient authorization.

## Manual test scenarios
1. Start a joint brokerage account request, provide joint-owner details, and wait for the summary.
2. Enter **“Change the base currency to SGD”** in the conversation box. Confirm the new summary shows SGD and a higher review version.
3. Confirm the edited application. The mock draft should show SGD.
4. Start another journey, change joint-owner tax residency to Singapore, and verify the revised summary before approval.
5. Reject a review and verify that no draft is created.
6. Try an unclear edit. The agent should ask for a specific field and value rather than silently changing state.

## Important limitations and controls
- Client profile and draft creation are mock implementations in `backend/graph.py`.
- The extraction fallback supports only a small set of common edits. LLM extraction quality depends on the configured model.
- `MemorySaver` is local-only; state is lost when the backend process restarts and it is not suitable for multi-instance deployment. Use a durable LangGraph checkpointer (for example, Postgres) before production.
- The Angular demo keeps the pending interrupt ID in component memory. A page refresh requires recovering the pending interrupt from server-side state before allowing a decision.
- Add authentication, authorization, CSRF/origin controls, rate limiting, audit, PII controls and entitlement checks before connecting real wealth APIs.
- Never use agent output as authorization. Draft submission and account opening must remain behind existing Java/Pega controls.
- This is a development starter, not a production-ready account-opening system.

## Next increments
1. Replace mock profile/draft functions with Java Experience API clients.
2. Add PostgreSQL checkpointing and persistent application state.
3. Propagate authenticated RM identity and entitlements into the workflow.
4. Integrate Pega workflow and downstream custody adapters.
5. Add integration tests, tracing, audit, retries and OpenShift deployment manifests.
