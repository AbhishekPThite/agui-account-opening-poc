from __future__ import annotations

import logging
import os
from typing import Any

from dotenv import load_dotenv
load_dotenv()

from langgraph.checkpoint.memory import MemorySaver

logger = logging.getLogger(__name__)

# Use the strict msgpack mode recommended for checkpoint deserialization.
os.environ.setdefault("LANGGRAPH_STRICT_MSGPACK", "true")

_pool: Any | None = None
_backend = os.getenv("CHECKPOINTER_BACKEND", "memory").strip().lower()


def build_checkpointer() -> Any:
    """Build a process-wide checkpointer. Postgres mode fails fast if misconfigured."""
    global _pool

    if _backend == "memory":
        logger.warning("Using MemorySaver: checkpoints will be lost when the process exits.")
        return MemorySaver()

    if _backend != "postgres":
        raise RuntimeError(
            "CHECKPOINTER_BACKEND must be either 'memory' or 'postgres'."
        )

    database_url = os.getenv("DATABASE_URL", "").strip()
    if not database_url:
        raise RuntimeError(
            "DATABASE_URL is required when CHECKPOINTER_BACKEND=postgres."
        )

    try:
        from langgraph.checkpoint.postgres import PostgresSaver
        from psycopg.rows import dict_row
        from psycopg_pool import ConnectionPool
    except ImportError as exc:
        raise RuntimeError(
            "PostgreSQL checkpointing dependencies are missing. "
            "Install backend/requirements.txt."
        ) from exc

    min_size = int(os.getenv("POSTGRES_POOL_MIN_SIZE", "1"))
    max_size = int(os.getenv("POSTGRES_POOL_MAX_SIZE", "10"))
    if min_size < 1 or max_size < min_size:
        raise RuntimeError("Invalid PostgreSQL pool size configuration.")

    _pool = ConnectionPool(
        conninfo=database_url,
        min_size=min_size,
        max_size=max_size,
        kwargs={
            "autocommit": True,
            "prepare_threshold": 0,
            "row_factory": dict_row,
        },
        open=True,
    )
    _pool.wait()

    saver = PostgresSaver(_pool)
    saver.setup()
    logger.info("PostgreSQL LangGraph checkpointer initialized and migrations verified.")
    return saver


def close_checkpointer() -> None:
    """Close the PostgreSQL connection pool during application shutdown."""
    if _pool is not None:
        _pool.close()
        logger.info("PostgreSQL checkpoint connection pool closed.")


checkpointer = build_checkpointer()


def checkpointer_backend() -> str:
    return _backend
