# Angular test client for AG-UI Account Opening POC

Small standalone Angular 19 app to exercise the FastAPI + LangGraph + AG-UI backend.

## Prerequisites
- Node.js 20.11+ (Node 22 LTS recommended)
- npm
- Backend from the parent repository

## 1. Start backend
From the repository's `backend/` folder:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

For a UI/protocol smoke test without the internal model, set `LLM_ENABLED=false` in `backend/.env`. To test the internal model, set `LLM_ENABLED=true`, provide `OPENAI_API_KEY`, and set `INTERNAL_CA_CERT` if required by your organization.

```bash
uvicorn main:app --reload --port 8000
```

## 2. Start Angular

The Angular workspace lives in `frontend/` at the repository root. Always start the dev server from that directory, not from the former `angular-test-client/` path.

From the repository root:

```bash
cd frontend
npm ci
npm start
```

Or, if dependencies are already installed:

```bash
cd frontend
npm start
```

Open http://localhost:4200. The Angular dev proxy forwards `/agent` to `http://localhost:8000`.

### If the dev server still reports paths under angular-test-client

1. Stop the old Angular process with `Ctrl+C` in the terminal where it is running.
2. Open a new terminal at the repository root and run `cd frontend`.
3. Confirm `pwd` ends with `/agui-account-opening-poc/frontend`.
4. Run `npm start` again.

The workspace configuration in `frontend/angular.json` expects `src/main.ts`, `src/styles.css` and `tsconfig.app.json`, all relative to `frontend/`. Do not copy these files back into the old directory or maintain a second Angular workspace.

## 3. Automated UI unit tests

Run the service-level unit tests from `frontend/`:

```bash
npm test
```

The suite covers conversation thread lifecycle and interrupt resumption, AG-UI event-to-state transitions, journey-state updates, and widget payload mapping. Tests use Node's built-in test runner and the existing esbuild toolchain; no browser is required.

## 4. Manual UI smoke test
1. Keep the default request: `Open a joint brokerage account for client C12345 with USD as base currency.`
2. Click **Start account opening**.
3. The agent should retrieve the mock profile and request joint-owner details.
4. Enter joint-owner name and tax residency.
5. Click **Submit joint-owner details**.
6. The graph should create a mock draft. Expand the AG-UI event trace to inspect events.

## Notes
- Local smoke-test only; do not enter real customer data.
- Client profile and draft creation are mocks; no real account is opened.
- The SSE adapter is deliberately minimal. Validate event schemas against your pinned `ag-ui-langgraph` version. The UI currently renders dynamic widgets from `STATE_SNAPSHOT`; if the backend emits deltas only, inspect the trace and add a state reducer or use the official AG-UI TypeScript SDK.
