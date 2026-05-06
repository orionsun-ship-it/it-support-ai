"""SQLModel engine + session helpers for the IT Ops API."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Iterator

from sqlmodel import Session, SQLModel, create_engine

# Resolve DB path. Default lives next to this file.
_DEFAULT_DB = Path(__file__).resolve().parent / "it_ops.db"
_DB_PATH = os.getenv("IT_OPS_DB_PATH", str(_DEFAULT_DB))

# SQLite needs check_same_thread=False so FastAPI's request workers can share
# the connection pool. We use NullPool indirectly via the default StaticPool
# fallback — SQLModel/SQLAlchemy handles this with the connect_args below.
DATABASE_URL = f"sqlite:///{_DB_PATH}"
engine = create_engine(
    DATABASE_URL,
    echo=False,
    connect_args={"check_same_thread": False},
)


def init_db() -> None:
    """Create all tables. Idempotent — safe to call on every startup."""
    Path(_DB_PATH).parent.mkdir(parents=True, exist_ok=True)
    SQLModel.metadata.create_all(engine)


def get_session() -> Iterator[Session]:
    """FastAPI dependency that yields a SQLModel session."""
    with Session(engine) as session:
        yield session
