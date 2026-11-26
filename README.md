# AG-UI Account Opening POC

A first vertical slice for an Angular + AG-UI + FastAPI + LangGraph account-opening experience.

## What this POC demonstrates

1. RM submits a natural-language account-opening request.
2. FastAPI exposes a LangGraph workflow through the AG-UI protocol.
3. The graph retrieves a **mock** client profile and determines missing joint-owner information.
4. The graph publishes a typed UI state describing the widget Angular should render.
5. Angular renders a controlled joint-owner form.
6. The RM submits the missing details; the graph creates a **mock draft**.

No real account is opened and no production system is called.

## Architecture

```text
Angular UI
  └── AG-UI adapter (fetch + SSE parsing)
        └── POST /agent
              └── ag-ui-langgraph
                    └── LangGraph workflow
                          ├── mock client profile tool
                          ├── account requirement checks
                          └── mock draft creation
```

## Prerequisites

- Python 3.11 or 3.12 recommended
- Node.js 20+
- Angular CLI matching your application version

The backend uses the official `ag-ui-langgraph` integration, which mounts a LangGraph graph as an AG-UI-compatible FastAPI endpoint.

## Run the backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

Health check: http://localhost:8000/health

AG-UI endpoint: `POST http://localhost:8000/agent`

## Connect the Angular files

Copy the files in `frontend/` into your Angular application. The sample component is standalone and uses Angular signals. If your application uses NgModules, declare/import it according to your existing conventions.

The sample uses a small fetch-based SSE adapter so it can be dropped into an existing Angular app without introducing a UI framework. It sends the AG-UI `RunAgentInput` shape and parses streamed AG-UI event frames. For a production implementation, prefer the official TypeScript client SDK and pin compatible SDK versions.

## POC request

Try:

```text
Open a joint brokerage account for client C12345 with USD as base currency.
```

The agent should return a mock client summary and request joint-owner details. Complete the rendered form and submit. The next run should create a mock draft.

## Important implementation notes

- This POC deliberately uses deterministic workflow logic; it does not require an LLM key.
- The client profile and draft creation functions are mock implementations in `backend/graph.py`.
- The `MemorySaver` checkpointer is for local demonstration only. Replace it with a durable checkpointer (for example, PostgreSQL) before multi-instance deployment.
- Add authentication, authorization, CSRF/origin controls, rate limiting, audit, PII controls and entitlement checks before connecting real wealth APIs.
- Do not use agent output as authorization. Draft submission and account opening must remain behind existing Java/Pega controls.
- The UI state is presentation guidance, not the authoritative business record.
- The POC currently models a draft, not final account submission or Pershing activation.

## Next increments

1. Replace mock client and draft functions with Java Experience API clients.
2. Add authenticated RM identity and entitlement propagation.
3. Persist business application state in the account-opening service.
4. Add durable LangGraph checkpointing and human approval interrupt/resume.
5. Add tests, tracing, audit, timeout/retry and deployment manifests.
