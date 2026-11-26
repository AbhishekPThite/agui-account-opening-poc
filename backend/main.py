from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from ag_ui_langgraph import add_langgraph_fastapi_endpoint

from graph import graph

app = FastAPI(title="Wealth Account Opening AG-UI POC", version="0.1.0")

# Local development only. Restrict origins to your actual Angular host in shared environments.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:4200"],
    allow_credentials=True,
    allow_methods=["POST", "GET", "OPTIONS"],
    allow_headers=["*"],
)

@app.get("/health")
async def health():
    return {"status": "ok", "service": "account-opening-agent"}

from ag_ui_langgraph import (
    LangGraphAgent,
    add_langgraph_fastapi_endpoint,
)

# graph is your compiled LangGraph workflow
agui_agent = LangGraphAgent(
    name="account-opening-agent",
    graph=graph,
    description="Wealth account opening assistant",
    emit_raw_events=False
)

add_langgraph_fastapi_endpoint(
    app,
    agui_agent,
    path="/agent"
)
