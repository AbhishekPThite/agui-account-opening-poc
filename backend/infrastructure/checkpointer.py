from __future__ import annotations

import logging
import os
from typing import Any

from dotenv import load_dotenv

load_dotenv()

from langgraph.checkpoint.memory import MemorySaver

logger = logging.getLogger(__name__)
os.environ.setdefault("LANGGRAPH_STRICT_MSGPACK", "true")

_pool: Any | None = None
_saver: Any | None = None
_backend = os.getenv("CHECKPOINTER_BACKEND", "memory").strip().lower()


def build_checkpointer() -> Any | None:
    """Return MemorySaver immediately; async PostgreSQL saver is created in app lifespan."""
    if _backend == "memory":
        logger.warning("Using MemorySaver: checkpoints will be lost when the process exits.")
        return MemorySaver()
    if _backend != "postgres":
        raise RuntimeError("CHECKPOINTER_BACKEND must be either 'memory' or 'postgres'.")
    if not os.getenv("DATABASE_URL", "").strip():
        raise RuntimeError("DATABASE_URL is required when CHECKPOINTER_BACKEND=postgres.")
    return None


async def setup_checkpointer() -> Any | None:
    """Create and initialize the async PostgreSQL saver inside the running event loop."""
    global _pool, _saver
    if _backend == "memory":
        return checkpointer

    database_url = os.getenv("DATABASE_URL", "").strip()
    try:
        from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
        from psycopg.rows import dict_row
        from psycopg_pool import AsyncConnectionPool
    except ImportError as exc:
        raise RuntimeError(
            "PostgreSQL checkpointing dependencies are missing. "
            "Install backend/requirements.txt."
        ) from exc

    min_size = int(os.getenv("POSTGRES_POOL_MIN_SIZE", "1"))
    max_size = int(os.getenv("POSTGRES_POOL_MAX_SIZE", "10"))
    if min_size < 1 or max_size < min_size:
        raise RuntimeError("Invalid PostgreSQL pool size configuration.")

    _pool = AsyncConnectionPool(
        conninfo=database_url,
        min_size=min_size,
        max_size=max_size,
        kwargs={
            "autocommit": True,
            "prepare_threshold": 0,
            "row_factory": dict_row,
        },
        open=False,
    )
    await _pool.open()
    await _pool.wait()
    # AsyncPostgresSaver captures the active event loop, so construct it here,
    # not at module import time.
    _saver = AsyncPostgresSaver(_pool)
    await _saver.setup()
    logger.info("Async PostgreSQL LangGraph checkpointer initialized and migrations verified.")
    return _saver


async def close_checkpointer() -> None:
    """Close the asynchronous PostgreSQL connection pool during application shutdown."""
    global _pool, _saver
    if _pool is not None:
        await _pool.close()
        _pool = None
        _saver = None
        logger.info("PostgreSQL checkpoint connection pool closed.")


checkpointer = build_checkpointer()


def checkpointer_backend() -> str:
    return _backend
