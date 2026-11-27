# AG-UI Account Opening POC

A first vertical slice for an Angular + AG-UI + FastAPI + LangGraph account-opening experience.

## What this POC demonstrates
1. RM submits a natural-language account-opening request.
2. FastAPI exposes a LangGraph workflow through the AG-UI protocol.
3. The graph retrieves a **mock** client profile and checks required fields deterministically.
4. The graph publishes typed UI state for Angular to render.
5. Angular renders a controlled joint-owner form and an application summary from the widget registry.
6. LangGraph pauses at an explicit human approval interrupt.
7. Angular resumes the same thread with the user's structured Confirm or Reject action.
8. The backend creates a **mock draft only after explicit approval**.

No real account is opened and no production system is called.

## Architecture
```text
Angular UI -> AG-UI adapter (fetch + SSE) -> FastAPI /agent
  -> ag-ui-langgraph -> LangGraph
       -> request understanding (internal LLM slot extraction)
       -> mock client profile -> deterministic requirements
       -> Angular form / summary UI state
       -> interrupt() waits for explicit human approval
       -> approved? -> mock draft creation : end without draft
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

## HITL approval flow
- When required fields are complete, the graph sets `approval_status=PENDING` and renders the application summary.
- The `await_human_approval` node calls LangGraph `interrupt()`; no draft-creation side effect occurs before the pause.
- FastAPI enables structured AG-UI interrupt outcomes so Angular receives the interrupt ID.
- Confirm resumes the same `threadId` with `resume: [{ interruptId, status: "resolved", payload: { action: "APPROVE", approved: true } }]`.
- Reject resumes the same interrupt with a rejection payload and ends without creating a draft.
- The draft node independently checks `approval_status == APPROVED` before creating the mock draft.

The approval payload is a POC interaction contract, not a production authorization mechanism. In production, bind the decision to an authenticated RM identity, application version/hash, entitlements, audit event and server-side approval policy. Never treat a browser-supplied boolean as sufficient authorization.

## Important limitations and controls
- Client profile and draft creation are mock implementations in `backend/graph.py`.
- `MemorySaver` is local-only; state is lost when the backend process restarts and it is not suitable for multi-instance deployment. Use a durable LangGraph checkpointer (for example, Postgres) before production.
- The Angular demo keeps the pending interrupt ID in component memory. A page refresh requires recovering the pending interrupt from server-side state before allowing a decision.
- Add authentication, authorization, CSRF/origin controls, rate limiting, audit, PII controls and entitlement checks before connecting real wealth APIs.
- Never use agent output as authorization. Draft submission and account opening must remain behind existing Java/Pega controls.
- This is a development starter, not a production-ready account-opening system.

## Next increments
1. Replace mock profile/draft functions with Java Experience API clients.
2. Propagate authenticated RM identity and entitlements into the workflow.
3. Persist application state in the account-opening service and use durable checkpointing.
4. Add integration tests, tracing, audit, retries and deployment manifests.
