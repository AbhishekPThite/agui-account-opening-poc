# AG-UI Account Opening POC

A vertical slice for an Angular + AG-UI + FastAPI + LangGraph account-opening experience.

## What this POC demonstrates
1. RM submits a natural-language account-opening request.
2. FastAPI exposes a LangGraph workflow through the AG-UI protocol.
3. The graph retrieves a client profile through the configurable Java Client Experience API adapter (mock mode by default) and checks required fields deterministically.
4. The graph publishes typed UI state for Angular to render through a controlled widget registry.
5. Angular renders a joint-owner form and application summary from metadata.
6. LangGraph pauses at an explicit human approval interrupt.
7. While paused, the RM can request field changes conversationally; the graph applies extracted updates, revalidates requirements and presents a new summary.
8. Every revised summary requires a fresh explicit approval.
9. Only an approved review reaches the Java Draft Application API adapter; local mock mode returns a simulated draft.
10. Checkpoints can be stored in PostgreSQL so thread state and pending interrupts survive backend restarts.

No real account is opened. The Java API adapter defaults to mock mode; HTTP mode is an explicitly configured hypothetical integration contract.

## Architecture
```text
Angular UI -> AG-UI adapter (fetch + SSE) -> FastAPI /agent
  -> ag-ui-langgraph -> LangGraph
       -> request understanding (LLM slot extraction)
       -> Java Client Experience API -> deterministic requirements
       -> Angular form / summary UI state
       -> interrupt() waits for human action
            | EDIT -> extract changes -> revalidate -> new summary -> interrupt()
            | APPROVE -> Java Draft Application Experience API
            | REJECT -> finish without draft
       -> Checkpointer
            | MemorySaver (local default)
            | AsyncPostgresSaver + async psycopg pool (durable)
```

## Prerequisites
- Python 3.12 (also compatible with 3.11)
- Node.js 20+
- Angular CLI matching your application version
- Docker Desktop / Docker Engine for the local PostgreSQL option

## Run backend
```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Set your internal model credentials in .env; never commit .env
uvicorn main:app --reload --port 8000
```
Health: http://localhost:8000/health  
AG-UI endpoint: `POST http://localhost:8000/agent`

## Configure durable PostgreSQL checkpointing

The default `CHECKPOINTER_BACKEND=memory` preserves the previous local behaviour. PostgreSQL mode uses `AsyncPostgresSaver` because the AG-UI adapter uses LangGraph's asynchronous state APIs. To test durable state:

1. Start the local PostgreSQL container from the repository root:

   ```bash
   docker compose -f backend/docker-compose.yml up -d
   ```

2. In `backend/.env`, set:

   ```dotenv
   CHECKPOINTER_BACKEND=postgres
   DATABASE_URL=postgresql://agui_poc:agui_poc_dev_only@localhost:5432/agui_poc
   POSTGRES_POOL_MIN_SIZE=1
   POSTGRES_POOL_MAX_SIZE=10
   LANGGRAPH_STRICT_MSGPACK=true
   ```

   The credentials above are for local development only. Use a managed PostgreSQL service, secret manager, TLS and a least-privilege database role in shared environments.

3. Install dependencies and restart FastAPI:

   ```bash
   pip install -r requirements.txt
   uvicorn main:app --reload --port 8000
   ```

4. Check the backend health response. It should report `"checkpointer": "postgres"`.

The application initializes the PostgreSQL connection pool and runs the LangGraph checkpoint schema migrations during startup. It uses `AsyncPostgresSaver` with Psycopg 3's `AsyncConnectionPool`, dictionary row factory, autocommit and prepared statements disabled for compatibility. The async pool and saver are created inside FastAPI's running lifespan event loop, and the graph is compiled after saver initialization. The pool is closed on application shutdown. PostgreSQL tables are created by the checkpointer's async `setup()` call.

## Persistence test — survive a backend restart

1. Start a new account-opening journey and reach the application summary / pending approval screen.
2. Keep the Angular browser tab open. Do not click Confirm or Reject.
3. Stop and restart only the FastAPI process. Do not stop or delete the PostgreSQL container.
4. Verify `GET /health` reports `"checkpointer": "postgres"`.
5. Use the existing review screen to request a supported account-detail edit.
6. Confirm that the same thread resumes, the saved fields remain present, and the revised summary reflects the change.
7. Confirm the revised summary and verify the mock draft contains the updated details.

This verifies persistence of LangGraph thread state and interrupt data across a backend process restart. The browser tab is deliberately kept open because the demo currently stores the thread ID and pending interrupt ID in Angular component memory. Refresh recovery and cross-device thread discovery are separate capabilities and are not implemented yet.

## Java Client Experience API — hypothetical contract (Milestone 5A)

The Python backend now calls a small adapter in `backend/enterprise_api.py`. The adapter defaults to mock mode so existing local journeys continue to work without a Java service. The same adapter now handles both client profile lookup and draft creation.

**Profile lookup contract**

```http
GET /api/v1/clients/{clientId}/profile
Authorization: Bearer <access-token>
Accept: application/json
```

Example response:

```json
{
  "clientId": "C12345",
  "displayName": "Alex Morgan",
  "segment": "PRIVATE_BANKING",
  "kycStatus": "VALID",
  "riskProfile": "MODERATE"
}
```

The response fields are illustrative and must be aligned to the actual Java OpenAPI contract later. The adapter validates the required fields and fails the workflow if the service returns an HTTP error or an invalid response; it does not silently substitute mock data after a real API failure.

**Draft creation contract**

```http
POST /api/v1/account-applications/drafts
Authorization: Bearer <access-token>
Idempotency-Key: <stable-per-review-key>
Content-Type: application/json
```

Example request:

```json
{
  "clientId": "C12345",
  "accountType": "BROKERAGE",
  "ownership": "JOINT",
  "jointOwner": {
    "name": "Jordan Morgan",
    "taxResidency": "Singapore"
  }
}
```

Example response:

```json
{
  "applicationId": "AO-1B722944",
  "status": "DRAFT",
  "clientId": "C12345"
}
```

The graph generates an idempotency key when it prepares each review summary and persists it in LangGraph state. The same key is sent on retries for that approved review. An edited application gets a new review version and a new key. The Java service must persist and enforce idempotency by key; the local mock adapter only simulates this within the running backend process.

The graph calls this endpoint only after the explicit approval interrupt returns APPROVED. HTTP errors, invalid response payloads, unexpected statuses and client-ID mismatches fail the run; the agent does not fabricate a successful draft.

**Configuration**

Keep the default mock mode while validating the existing POC:

```dotenv
JAVA_API_MODE=mock
JAVA_API_BASE_URL=http://localhost:8081
JAVA_API_BEARER_TOKEN=
JAVA_API_TIMEOUT_SECONDS=15
JAVA_API_CA_CERT=
```

To exercise the hypothetical HTTP contract against a Java service or stub:

```dotenv
JAVA_API_MODE=http
JAVA_API_BASE_URL=https://java-experience-api.example.internal
JAVA_API_BEARER_TOKEN=<local-development-token>
JAVA_API_TIMEOUT_SECONDS=15
JAVA_API_CA_CERT=/path/to/internal-ca.crt
```

Do not put real tokens in source control or share them in chat. The bearer-token setting is a local POC placeholder, not the final enterprise authentication design. In production, use PingFederate/OAuth token acquisition or trusted delegated-token propagation, audience/scope validation, service identity, TLS and secret management.

**Current milestone boundary:** both client profile retrieval and draft creation are routed through this adapter. In mock mode, draft idempotency is simulated in process memory; the Java service must enforce durable idempotency in HTTP mode. No Pega or Pershing endpoint is called directly by LangGraph.

## Internal model endpoint
The POC uses `langchain-openai` against an OpenAI-compatible internal endpoint. Configure `OPENAI_BASE_URL`, `OPENAI_MODEL`, and `OPENAI_API_KEY` in `backend/.env`. Set `INTERNAL_CA_CERT` to your organization's CA certificate path if required. TLS verification remains enabled.

Set `LLM_ENABLED=false` to test the protocol using deterministic regex fallback without calling the model. The model is used only for intent/slot extraction; it does not decide KYC eligibility, business validation, authorization, suitability, or transaction approval.

## Conversational review and HITL
- When required fields are complete, the graph sets `approval_status=PENDING` and renders the application summary.
- The `await_human_approval` node calls LangGraph `interrupt()`; no draft-creation side effect occurs before the pause.
- The review interrupt supports three explicit actions:
  - `APPROVE`: resume and call the Draft Application Experience API adapter.
  - `REJECT`: resume and finish without a draft.
  - `EDIT`: resume with a natural-language change request, extract only non-empty fields, update the checkpointed state, re-run client lookup and deterministic requirement checks, then render a new summary.
- Every edited summary increments `reviewVersion` and requires a new approval interrupt. Previous approval does not carry forward.
- Angular resumes the same `threadId` with the interrupt ID and structured payload. The LLM does not decide approval.

The approval payload is a POC interaction contract, not a production authorization mechanism. The draft adapter's idempotency key protects retry behaviour, but it does not replace server-side approval authorization. In production, bind the decision to an authenticated RM identity, application version/hash, entitlements, audit event and server-side approval policy. Never treat a browser-supplied boolean as sufficient authorization.

## Manual conversational test scenarios
1. Start a joint brokerage account request, provide joint-owner details, and wait for the summary.
2. Enter a supported account-detail change in the conversation box. Confirm the new summary reflects the change and shows a higher review version.
3. Confirm the edited application. The draft confirmation should show the API-returned application ID and status.
4. Start another journey, change joint-owner tax residency to Singapore, and verify the revised summary before approval.
5. Reject a review and verify that no draft is created.
6. Try an unclear edit. The agent should ask for a specific field and value rather than silently changing state.

## Important limitations and controls
- Java Client and Draft Application Experience API integration is configurable; mock mode is the default. The HTTP contract and response fields are hypothetical and must be aligned with the real Java OpenAPI specification before production use. Mock draft idempotency is process-local only; the Java API must implement durable key storage.
- The extraction fallback supports only a small set of common edits. LLM extraction quality depends on the configured model.
- PostgreSQL checkpointing persists LangGraph state and interrupts, but does not replace a business-owned application database or audit system. Keep authoritative application records and approval evidence in the appropriate Java/Pega services.
- The local Docker Compose credentials are intentionally simple and must never be used outside local development.
- `MemorySaver` remains the default unless `CHECKPOINTER_BACKEND=postgres` is selected.
- The Angular demo keeps the thread ID and pending interrupt ID in component memory. A page refresh requires recovering the pending interrupt from server-side state before allowing a decision.
- Add authentication, authorization, CSRF/origin controls, rate limiting, audit, PII controls and entitlement checks before connecting real wealth APIs.
- Never use agent output as authorization. Draft submission and account opening must remain behind existing Java/Pega controls.
- This is a development starter, not a production-ready account-opening system.

## Next increments
1. Align the hypothetical Java API contracts with the real OpenAPI specifications and authentication model.
2. Add authenticated thread ownership, refresh recovery and durable application identifiers.
3. Propagate authenticated RM identity and entitlements into the workflow.
4. Integrate Pega workflow and downstream custody adapters.
5. Add integration tests, tracing, audit, retries and OpenShift deployment manifests.
