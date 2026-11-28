# AG-UI Account Opening POC

A vertical slice for an Angular + AG-UI + FastAPI + LangGraph account-opening experience.

## What this POC demonstrates
1. RM submits a natural-language account-opening request.
2. FastAPI exposes a LangGraph workflow through the AG-UI protocol.
3. The graph retrieves a client profile through the configurable Java Client Experience API adapter (mock mode by default) and checks required fields deterministically.
4. The graph publishes typed UI state for Angular to render through a controlled widget registry.
5. Angular renders adaptive profile, joint-owner, optional beneficiary and mandatory risk-assessment forms plus the application summary from metadata.
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
  "riskProfile": "MODERATE",
  "personalDetails": {"firstName": "Alex", "lastName": "Morgan", "dateOfBirth": "1982-04-18", "email": "alex.morgan@example.test", "phone": "+1-212-555-0142"},
  "addresses": {"residential": {"line1": "100 Park Avenue", "line2": "Apt 12B", "city": "New York", "state": "NY", "postalCode": "10017", "country": "US"}, "mailingSameAsResidential": true, "mailing": null},
  "taxResidencies": [{"country": "US", "taxIdType": "SSN", "taxIdMasked": "***-**-6789", "status": "DECLARED"}],
  "employment": {"status": "EMPLOYED", "occupation": "Technology Executive", "employerName": "Example Financial Services", "industry": "FINANCIAL_SERVICES"},
  "investmentProfile": {"experienceLevel": "EXPERIENCED", "investmentObjectives": ["GROWTH", "INCOME"], "riskTolerance": "MODERATE", "annualIncomeRange": "250K_500K", "netWorthRange": "1M_5M"}
}
```

The response fields are an assumed POC contract and must be aligned to the actual Java OpenAPI specification later. The adapter validates the required profile sections and fails the workflow if the service returns an HTTP error or an invalid response; it does not silently substitute mock data after a real API failure.

**Adaptive profile assessment (Milestone 7)**

After account setup, the graph retrieves this profile and classifies attributes into Completed, Confirmation required and Action required. Populated personal, address, tax residency, employment and investment-profile values are shown for confirmation. Required attributes missing from the response block confirmation.

**Adaptive data capture (Milestone 7B)**

- The dashboard offers a profile review/update action. The generated form contains populated fields that require explicit confirmation or correction, plus only missing mandatory fields.
- A completed submission is merged into two separate workflow buckets: `confirmed_profile_data` and `application_data`. The retrieved `client_profile` response remains unchanged.
- After submission, the backend retrieves the profile again, reapplies the confirmed application-level overlay, and deterministically reassesses completeness. The RM can then confirm the profile and continue.
- The draft request carries the confirmed values under `applicationData`; align this assumed field with the actual Java OpenAPI contract.
- Optional fields that are absent are not requested by this increment. Conditional product/registration-specific fields and richer field types are future extensions.
- KYC status is displayed as retrieved information, not treated as an approval. Profile completeness is assessed deterministically; the LLM does not invent client facts or decide eligibility.

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
  "applicationData": {
    "Personal details|email": "alex.morgan@example.test",
    "Residential address|city": "New York"
  },
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

## Adaptive profile capture test

1. Start an account-opening journey and reach the profile assessment dashboard.
2. Select **Review or update profile details**. The generated form should show populated profile attributes for confirmation/correction and only missing mandatory attributes for completion.
3. Change a populated value and fill any required missing values. Submit the form.
4. Verify the profile dashboard is recalculated, missing mandatory fields are no longer listed, and the original mock Client Experience API response remains unchanged.
5. Select **Confirm profile and continue**. The journey should proceed to the account-specific requirements and application review.
6. Inspect the draft request in backend logs or a Java stub and verify the confirmed values are carried in `applicationData`.

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


## Registration requirements decision engine (Milestone 8A)

The backend resolves a deterministic requirements matrix from the selected registration type. The rules are maintained in `backend/requirements_engine.py`; they are not inferred by the LLM.

| Requirement | Individual | Individual TOD | Joint | Joint TOD |
|---|---|---|---|---|
| Primary owner details | Mandatory | Mandatory | Mandatory | Mandatory |
| Joint owner details | Not required | Not required | Mandatory | Mandatory |
| Beneficiary details | Optional | Optional | Optional | Optional |
| Client profile confirmation | Mandatory | Mandatory | Mandatory | Mandatory |
| Risk assessment | Mandatory | Mandatory | Mandatory | Mandatory |

The engine returns a normalized requirement list with `key`, `label`, `status` and `required`. The graph uses the resolved joint-owner rule to decide whether the joint-owner form is needed and includes the resolved matrix in the application review summary. Beneficiary details do not block the journey and are captured in the optional 8B step.

**Milestone boundary:** 8A establishes and tests the decision matrix. The client-profile confirmation gate remains separate. Risk assessment is now implemented as the mandatory Milestone 8C capture and completion gate. The POC validates completeness but does not make a suitability decision.

Run the decision-engine unit tests from the backend directory:

```bash
python -m unittest tests.unit.domain.test_requirements_engine -v
```


## Angular journey progress tracker (Milestone 8E.2)

The Angular shell renders a responsive five-stage progress tracker whenever the backend includes `ui.journeyStatus`. It displays Profile, Account Details, Risk Profile, Features and Summary, along with the current status and completed-stage count.

The tracker is presentation-only: Angular does not calculate or mutate workflow progress. It consumes the backend's stage statuses and renders them with accessible list semantics. On narrow screens, the tracker switches to a vertical layout.

## Angular journey progress tracker (Milestone 8E.2)

Angular reads `ui.journeyStatus` from each AG-UI state snapshot and renders a persistent five-stage progress tracker above the active workflow widget.

The tracker displays:
- Profile, Account Details, Risk Profile, Features and Summary.
- The backend-calculated stage status, current stage and completed-stage count.
- A completion progress bar and status legend.
- A responsive horizontal layout on wider screens and a vertical layout on narrow screens.
- Accessible progress-bar values and current-step semantics.

The frontend does not calculate workflow completion or decide which stages are mandatory. It renders the status model supplied by LangGraph. The active form/widget and existing submit actions are unchanged.

After pulling the changes, start the backend and Angular client as usual. Begin a new journey to receive fresh state snapshots containing the current `journeyStatus` model.

## Journey status model (Milestone 8E.1)

The backend now derives a compact journey-progress model from LangGraph state and attaches it to each rendered UI payload as `ui.journeyStatus`.

The model includes:
- Ordered stages: Profile, Account Details, Risk Profile, Features and Summary.
- Per-stage status: `COMPLETED`, `ACTION_REQUIRED`, `CONFIRMATION_REQUIRED`, `IN_PROGRESS` or `PENDING`.
- `currentStage`, `completedCount`, `totalCount` and `overallStatus`.

Status is deterministic and based on workflow flags, profile assessment and registration type. In particular, joint-owner completion is required only for Joint and Joint TOD; optional beneficiary capture does not block the Account Details stage. Summary becomes complete only when the draft confirmation widget is produced.

This increment exposes the backend model only. The Angular progress tracker and navigation are the next 8E increments.

Run from the backend directory:

```bash
python -m unittest tests.workflow.test_journey_status -v
```

## Product-specific feature capture (Milestone 8D)

After the mandatory risk-assessment step, the graph renders a feature form selected deterministically from the account product type.

**Brokerage**
- Cash Sweep Options: Sweep Vehicle defaults to **BDP**; existing banking-account link is left blank because the screenshot does not show a selected account.
- Options Settings: “Opt in to Options?” defaults to **No**.
- Tax Lot Relief Methods: Mutual Funds defaults to **First In First Out (FIFO)**.
- Tax Lot Relief Methods: All Other Securities defaults to **First In First Out (FIFO)**.

The defaults mirror the values visible in the supplied Brokerage - Individual screenshot. The existing-banking-account field is intentionally unselected. These are presentation defaults for the POC, not product eligibility or trading permissions.

**Credit Facility**
- Requested credit limit: positive numeric amount.
- Proposed collateral: `SECURITIES`, `CASH` or `OTHER`.
- Facility purpose: `LIQUIDITY`, `INVESTMENT` or `OTHER`.

The product feature schemas live in `backend/requirements_engine.py`. The backend selects a lightweight schema from the already-selected product. Brokerage preferences are captured generically without adding product-policy logic to the graph; the credit facility form retains basic required-field and positive-amount validation. The graph cannot prepare the application review until the selected product's feature form is completed. The submitted values are checkpointed, shown in the review summary and sent to the Draft Application API under `productFeatures`. The local mock draft response echoes this object.

These are illustrative POC capture fields, not approved product terms, credit underwriting criteria or collateral acceptance rules. Align detailed option sets and validation with the actual product catalog, jurisdiction, risk controls and Java OpenAPI contract before production.

Run backend tests from the backend directory:

```bash
python -m unittest tests.unit.domain.test_requirements_engine tests.unit.domain.test_risk_assessment tests.unit.domain.test_product_features -v
```

Manual checks:
1. Start a new Brokerage journey and complete profile, owner, beneficiary and risk steps. Verify the Brokerage form defaults Sweep Vehicle to BDP, Options election to No, and both tax-lot methods to First In First Out; the existing banking-account link remains blank.
2. Complete it and verify the application summary contains `productFeatures`.
3. Start a new Credit Facility journey and verify the form instead contains requested credit limit, proposed collateral and facility purpose.
4. Submit zero or a negative credit limit using a direct structured request and verify the backend rejects it.
5. Verify the approved mock draft request/response carries the selected product features.

## Mandatory risk assessment (Milestone 8C)

After owner and optional beneficiary capture, the graph presents a mandatory risk-assessment form before it can prepare the application review.

- Existing investment objectives, experience level and risk tolerance are prepopulated from the Client Experience API profile. The root `riskProfile` is used as a fallback for risk tolerance.
- The RM confirms or corrects the prepopulated values and supplies any missing required information.
- The POC captures investment objectives, time horizon, liquidity needs and risk comfort level.
- The backend validates that every field is present and that enumerated answers use supported values. Investment objectives are normalized to an uppercase list.
- The graph persists the submitted values in checkpointed workflow state and includes them under `riskAssessment` in the Draft Application API request and application review summary.
- The graph cannot proceed to application review until a complete risk assessment has been submitted.
- This is data capture and completeness validation only. It does not calculate a risk score, assess suitability, recommend products, determine eligibility or replace the firm's approved suitability process.

The field set and enumerations are assumed POC contracts. Align them with the firm's approved risk questionnaire, client segment, product and jurisdiction requirements before production.

Run the backend tests from the backend directory:

```bash
python -m unittest tests.unit.domain.test_requirements_engine tests.unit.domain.test_risk_assessment -v
```

Manual check:
1. Start a journey and complete profile confirmation, any required joint-owner information and the beneficiary step.
2. Verify the risk form prepopulates investment objectives, experience and risk tolerance from the mock client profile.
3. Verify time horizon and liquidity needs are required if not already present.
4. Submit incomplete data through the UI and verify the browser prevents submission. Also verify the backend rejects incomplete structured submissions.
5. Submit all fields and verify the application summary includes `riskAssessment`.
6. Approve the review and inspect the mock draft response/logs to confirm the draft request includes `riskAssessment`.

## Adaptive owner and beneficiary capture (Milestone 8B)

- **Primary owner:** uses the client profile retrieved through the Client Experience API. The existing profile confirmation/capture gate is reused; confirmed or corrected values remain in `applicationData`.
- **Joint owner:** the graph asks for joint-owner name and tax residency only for `JOINT` and `JOINT_TOD`. The form prepopulates any values already present in workflow state.
- **Beneficiary:** after owner requirements are satisfied, the graph offers an optional beneficiary form for all four registration types. The POC captures one beneficiary's full name, relationship and date of birth. All fields are optional, and the RM can explicitly skip the step.
- **Draft payload:** when beneficiary data is supplied, it is sent as a one-element `beneficiaries` array. When skipped or left blank, the field is omitted from the request. The mock response echoes the beneficiary list.
- **Source boundary:** the one-beneficiary field set and Java payload shape are assumed POC contracts, not a legal or jurisdictional beneficiary standard. Align them with the actual Java OpenAPI contract and applicable product/jurisdiction rules before production.
- **No eligibility decision:** beneficiary data is captured as application input only. It does not trigger eligibility, suitability, legal validation or account-opening decisions.

Manual checks:
1. Start an Individual journey: primary-owner data is taken from the confirmed client profile; no joint-owner form appears.
2. Start a Joint journey: the joint-owner form appears and is required before the beneficiary step.
3. On either journey, add a beneficiary and verify the draft request includes `beneficiaries`.
4. Repeat and select **Skip beneficiary**; the journey must proceed and the draft request must omit `beneficiaries`.
5. Try submitting the beneficiary form with all fields blank; it should also proceed without blocking.


## Conversational account setup prefill (Milestone 9A)

The Account Setup screen now supports conversational prefill. While the `ACCOUNT_SETUP_FORM` is active, the RM can describe the desired account in the chat panel, for example:

> Make this a joint brokerage account with margin enabled and call it Family Portfolio.

The reusable account-request extractor returns only supported account setup fields:
- Product: `BROKERAGE` or `CREDIT_FACILITY`.
- Registration: `INDIVIDUAL`, `INDIVIDUAL_TOD`, `JOINT` or `JOINT_TOD`.
- Account nickname: explicitly stated text.
- Margin: `NONE` or `MARGIN`.

LangGraph validates enum values and merges only extracted values into the checkpointed state. Unmentioned values remain unchanged. The next UI state snapshot carries those values as form defaults, and Angular refreshes the visible form from that backend snapshot. The RM must still review the fields and select **Continue**; a chat message never submits the form or marks account setup complete.

This increment uses the configured LLM through the account-request extraction path. The unified conversational journey assistant now routes messages to the active step's extractor and supports step-specific questions and form prefill.

Run the focused backend tests from the backend directory:

```bash
python -m unittest tests.workflow.test_conversational_account_setup -v
```

Manual check:
1. Start a new journey and wait for the Account Setup form.
2. Enter: `Make this a joint brokerage account with margin enabled and call it Family Portfolio.`
3. Select **Prefill account setup** and verify Product, Registration, Nickname and Margin are populated.
4. Enter a follow-up: `Change the nickname to Family Brokerage.` Verify only the nickname changes and the other values remain.
5. Verify the form is not submitted until you select **Continue**.

## Conversational risk assessment prefill (Milestone 9B)

While the mandatory Risk Assessment form is active, the RM can describe client-stated preferences in natural language. The configured model extracts only the four questionnaire fields:
- Investment objectives.
- Investment time horizon.
- Liquidity needs.
- Risk tolerance.

Only non-empty extracted values are merged into the checkpointed risk-assessment state. Follow-up messages can update one field without clearing the others. Unsupported or ambiguous enum values are ignored by the extractor and remain available for manual selection in the form. The next AG-UI state snapshot refreshes the form defaults.

The conversational message does **not** submit the risk assessment or mark it complete. The RM must review the populated form and select Continue. The backend still validates all four required fields and the supported enum values on structured form submission.

**Control boundary:** this is extraction of client-stated information only. The model must not calculate a risk score, infer a risk category from demographics or financial data, assess suitability, recommend investments, or make eligibility decisions. The questionnaire's field definitions and enum values are assumed POC contracts and must be aligned with the firm's approved risk process before production.

Run the focused backend tests from the backend directory:

```bash
python -m unittest tests.unit.domain.test_risk_assessment -v
```

Manual check:
1. Start a new journey and reach Risk Assessment.
2. Enter: `I am investing for about seven years, need medium liquidity, and am comfortable with moderate risk. My objectives are growth and income.`
3. Select **Prefill risk assessment**. Verify that the form fields are populated but not submitted.
4. Enter a follow-up that changes only liquidity needs. Verify the other fields remain populated.
5. Submit with a required field blank and verify the backend still rejects it; complete all fields and continue.
6. Try ambiguous language such as `I may need access to the money sometime`. Verify the model leaves the unclear field blank rather than inventing an answer.

## Conversational product feature prefill (Milestone 9C)

While the product-specific feature form is active, the RM can describe the client's stated preferences in natural language. The extractor receives the selected product's schema from `requirements_engine.py`, so it only considers fields and enum options valid for that product.

**Brokerage examples**
- “Opt in to options.”
- “Use last in first out for mutual funds.”
- “Link the existing banking account ending 1234.”

**Credit Facility example**
- “Request 250,000 against securities for liquidity.”

Only non-empty supported values are merged into the checkpointed `product_features` state. Follow-up messages preserve all fields not mentioned. Unsupported select values and non-positive or non-numeric amounts are ignored; the RM can correct them in the form. The next AG-UI state snapshot refreshes the form defaults.

Conversational input does **not** submit or complete the form. The RM must review the values and select Continue. The backend continues to validate required Credit Facility fields, positive requested limit and supported select options on structured form submission. Brokerage fields remain optional as defined by the current POC schema.

**Control boundary:** the model captures stated preferences only. It does not approve options permissions, determine collateral acceptability, approve a credit limit, perform underwriting, assess eligibility or make suitability decisions. The feature schema and Java API payload are assumed POC contracts and must be aligned with the approved product catalog and actual Java OpenAPI contract before production.

Run focused backend tests from the backend directory:

```bash
python -m unittest tests.unit.domain.test_product_features -v
```

Manual checks:
1. Start a Brokerage journey and reach Product Features. Enter: `Opt in to options and use last in first out for mutual funds.`
2. Select **Prefill product features**. Verify only those stated fields change and defaults/previous values remain.
3. Send a follow-up changing only the other-securities tax-lot method. Verify the options election and mutual-funds method remain unchanged.
4. Start a Credit Facility journey. Enter: `Request 250000 against securities for liquidity.` Verify all three fields are prefilled but the form is not submitted.
5. Try an unsupported collateral value or a negative amount. Verify it is not accepted as a valid prefill; structured submission must still be rejected if required values are missing or invalid.
6. Complete the form explicitly and verify the application summary and draft request include `productFeatures`.

## Unified conversational journey assistant (Milestone 9D)

The Angular client now presents one conversation panel throughout the active account-opening journey instead of separate chat panels for Account Setup, Risk Assessment and Product Features. The same interface can also be used during application review to request a change; review changes still resume the existing LangGraph approval interrupt and require a fresh summary and explicit approval.

The assistant is aware of the active UI step:
- Account Setup: captures product, registration, nickname and margin preferences.
- Client profile assessment: answers questions about the current profile-review step. Use the profile review controls to confirm or request profile data capture.
- Profile data capture, joint-owner details and beneficiary details: extracts values from the currently rendered form fields.
- Risk Assessment: uses the dedicated risk-field extractor.
- Product Features: uses the selected product's feature schema.
- Application review: accepts edits through the existing interrupt/resume flow.

If the message does not yield a supported field value, the assistant answers a question about the active step. It uses the current step title, description and field definitions as context. It does not claim to update the form when it has only answered a question. A question-only response leaves the current screen in place.

**Workflow controls remain authoritative:** conversational messages do not submit forms, complete mandatory stages, approve applications or create drafts. The RM must use the relevant form action. Risk, product-feature, client-profile, and draft gates remain in place. The assistant must not make KYC, suitability, legal/tax, credit, collateral, permissions or eligibility decisions.

The generic active-form extractor is constrained to the fields and select options provided by the current UI metadata. It captures explicit values only and ignores unsupported enum values and invalid positive-number inputs. The POC still relies on the configured LLM for conversational extraction and question answering; if the model is disabled, the unified panel remains available but natural-language capture falls back to the form and step guidance is generic.

Run focused tests from the backend directory:

```bash
python -m unittest tests.workflow.test_unified_journey_assistant -v
python -m unittest tests.workflow.test_conversational_account_setup tests.unit.domain.test_risk_assessment tests.unit.domain.test_product_features -v
```

Manual checks:
1. Start a journey and use the same conversation panel on Account Setup to ask what a field means; verify the form remains visible.
2. Describe a joint-owner name while the Joint Owner form is active; verify only that field is populated and tax residency is retained.
3. Ask a question on the Client Profile assessment screen; verify the assistant explains the step without skipping the profile confirmation controls.
4. On Risk Assessment and Product Features, use natural language to prefill fields and then ask a question; verify both actions use the same panel.
5. During application review, request a change. Verify the graph resumes the pending interrupt, generates a revised summary and requires a new explicit approval.
6. Verify no conversational message alone completes a required stage or creates a draft.



### Upfront conversational prefill across the journey

The first natural-language request is used to extract explicit values for account setup, risk assessment and product features (when the product type is identified). Risk and product-feature values are stored in workflow state and rendered as defaults when those later screens are reached. This is prefill only: mandatory forms still require explicit review and submission, and no suitability, eligibility or approval decision is made by the LLM.


## Milestone 10A.1 – Dashboard-first backend workspace

The initial account-opening request now retrieves the client profile and presents an APPLICATION_DASHBOARD workspace instead of forcing the user through the account setup, profile, risk and feature screens in sequence.

The backend dashboard model exposes section-level status and descriptions for PROFILE, ACCOUNT_DETAILS, RISK_PROFILE, FEATURES and SUMMARY.

A structured DASHBOARD_NAVIGATION request can open PROFILE, ACCOUNT_DETAILS, RISK_PROFILE, FEATURES or SUMMARY. Section navigation prepares the existing section widget from persisted LangGraph state; it does not mark the section complete. Account Details opens the joint-owner form when setup is already complete but required joint-owner details are missing. Product Features cannot be opened until a product is selected.

Final application review is guarded: the summary section returns to the dashboard with an explanation until the required sections are complete. Explicit approval and draft creation remain separate gates.

Backend regression tests cover dashboard statuses, direct section opening and the final-review guard. Run:

```bash
cd backend
python -m unittest tests.workflow.test_journey_status -v
```

The Angular dashboard navigation controls are the next increment (10A.2).


## Milestone 10A.2 – Angular dashboard-first experience

The Angular client now renders the APPLICATION_DASHBOARD as the primary account-opening workspace. It shows client/product context, overall completion, and clickable section cards for Client Profile, Account Details, Risk Profile, Features and Summary. Each card displays its backend-calculated status and a short description.

Selecting a card sends a structured DASHBOARD_NAVIGATION message on the same AG-UI thread. The backend opens the requested section using the checkpointed application state. A section form remains visible until explicitly submitted; after submission, the backend returns the user to the dashboard with refreshed status. The section workspace includes a Back to application dashboard action. The Dashboard action is also supported by the backend for direct return.

The Summary card remains subject to backend readiness checks. Opening it before the required sections are complete returns the dashboard with an explanation. The explicit application approval interrupt and draft-creation gate are unchanged.

Manual checks:
1. Start a new journey. Verify the first workspace is the section dashboard rather than a sequential form.
2. Open Client Profile, return to the dashboard, and verify the section status remains accurate.
3. Open Account Details, change the registration or nickname, submit, and verify the dashboard returns with updated context/status.
4. Open Risk Profile and Features directly. Verify previously captured values are prepopulated; submit and verify the dashboard returns.
5. For Joint or Joint TOD, open Account Details and verify missing joint-owner information is presented.
6. Select Summary before completing mandatory sections; verify the dashboard remains visible and explains what is outstanding.
7. Complete all required sections, open Summary, and verify the existing explicit approval action is still required before draft creation.

The Angular build and browser workflow must be verified locally after pulling; these changes were committed through GitHub and were not built in the user's environment.


### 10A.2 Angular dashboard navigation and section workspace

The Angular client now treats the application dashboard as the main workspace. The dashboard displays client context, a completion percentage, and clickable cards for Client Profile, Account Details, Risk Profile, Product Features and Summary. Each card renders its status and description from the backend journey-status model.

Clicking a card sends a structured DASHBOARD_NAVIGATION message on the existing AG-UI thread. The selected section opens using checkpointed LangGraph state. A Back to application dashboard control is available while editing a section. After an explicit form submission, the backend returns the dashboard and publishes refreshed status. Joint-owner details are submitted through a structured form payload and validated server-side.

The Product Features section remains unavailable until a product is selected. Summary navigation remains protected by the backend's mandatory-section readiness check and existing approval interrupt. The dashboard is not an approval surface and cannot create a draft.

Manual verification after pulling:
- Start a new journey and confirm the dashboard is the first workspace.
- Open each section from its card and return using the back control.
- Submit Account Details, Risk Profile and Product Features; confirm each returns to the dashboard and preserves previously entered values.
- For Joint and Joint TOD, verify the Joint Owner form appears when required and rejects missing name or tax residency.
- Open Summary early and verify the dashboard explains which required sections remain incomplete.
- Complete all required sections, open Summary, and confirm the explicit approval gate still appears before draft creation.



## Repository layout (refactored)

- `backend/workflow/nodes.py` contains workflow node implementations.
- `backend/workflow/graph.py` contains LangGraph topology and routing.
- `backend/workflow/state.py` defines the shared LangGraph state contract; application code and tests import workflow nodes and routing directly from their owning modules.
- `backend/tests/unit/domain/`, `backend/tests/unit/application/` and `backend/tests/workflow/` organize the regression suite.
- `frontend/` is the Angular workspace (formerly `angular-test-client/`); the integration notes remain alongside it.

Run the complete backend regression suite from `backend/`:

```bash
python -m unittest discover -s tests -t . -v
```

Build the Angular client from `frontend/`:

```bash
npm ci
npm run build
```
