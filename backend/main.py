import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from ag_ui_langgraph import LangGraphAgent, add_langgraph_fastapi_endpoint

logging.basicConfig(level=logging.INFO)

from checkpointer import (
    checkpointer_backend,
    close_checkpointer,
    setup_checkpointer,
)
from graph import build_graph


@asynccontextmanager
async def lifespan(app: FastAPI):
    saver = await setup_checkpointer()
    graph = build_graph(checkpointer_override=saver)
    agui_agent = LangGraphAgent(
        name="account-opening-agent",
        graph=graph,
        description="Wealth account opening assistant",
        emit_raw_events=False,
        emit_interrupt_outcome=True,
    )
    add_langgraph_fastapi_endpoint(app, agui_agent, path="/agent")
    try:
        yield
    finally:
        await close_checkpointer()


app = FastAPI(
    title="Wealth Account Opening AG-UI POC",
    version="0.3.2",
    lifespan=lifespan,
)

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
    return {
        "status": "ok",
        "service": "account-opening-agent",
        "checkpointer": checkpointer_backend(),
    }
