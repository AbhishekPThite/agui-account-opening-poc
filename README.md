# AG-UI Account Opening POC

A first vertical slice for an Angular + AG-UI + FastAPI + LangGraph account-opening experience.

## What this POC demonstrates
1. RM submits a natural-language account-opening request.
2. FastAPI exposes a LangGraph workflow through the AG-UI protocol.
3. The graph retrieves a **mock** client profile and checks required fields.
4. The graph publishes typed UI state for Angular to render.
5. Angular renders a controlled joint-owner form.
6. The graph creates a **mock draft** when required fields are present.

No real account is opened and no production system is called.

## Architecture
```text
Angular UI -> AG-UI adapter (fetch + SSE) -> FastAPI /agent
  -> ag-ui-langgraph -> LangGraph
       -> request understanding (internal LLM slot extraction)
       -> mock client profile -> deterministic requirements
       -> Angular UI state -> mock draft creation
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
The POC uses `langchain-openai` against an OpenAI-compatible internal endpoint. Configure `OPENAI_BASE_URL`, `OPENAI_MODEL`, and `OPENAI_API_KEY` in `backend/.env`. The example file contains the endpoint/model previously supplied. Set `INTERNAL_CA_CERT` to your organization's CA certificate path if required. TLS verification remains enabled.

Set `LLM_ENABLED=false` to test the protocol using deterministic regex fallback without calling the model. The model is used only for intent/slot extraction; it does not decide KYC eligibility, business validation, authorization, suitability, or transaction approval.

## Connect Angular
Copy `frontend/` into your Angular application. The sample standalone component uses Angular signals and a small fetch-based SSE adapter. For production, prefer the official TypeScript AG-UI client SDK and pin compatible versions.

## Example request
```text
Open a joint brokerage account for client C12345 with USD as base currency.
```

The mock flow returns a client summary and requests joint-owner details. Submitting those details creates a mock draft.

## Important limitations and controls
- Client profile and draft creation are mock implementations in `backend/graph.py`.
- `MemorySaver` is local-only; replace it with durable checkpointing before multi-instance deployment.
- Add authentication, authorization, CSRF/origin controls, rate limiting, audit, PII controls and entitlement checks before connecting real wealth APIs.
- Never use agent output as authorization. Draft submission and account opening must remain behind existing Java/Pega controls.
- This is a development starter, not a production-ready account-opening system.

## Next increments
1. Replace mock profile/draft functions with Java Experience API clients.
2. Propagate authenticated RM identity and entitlements.
3. Persist application state in the account-opening service.
4. Add durable checkpointing and human approval interrupt/resume.
5. Add integration tests, tracing, audit, retries and deployment manifests.
