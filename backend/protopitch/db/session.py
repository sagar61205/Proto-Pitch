"""Engine and session factory. SQLite runs in WAL mode with foreign keys enforced."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import Session, sessionmaker


def make_engine(database_url: str) -> Engine:
    is_sqlite = database_url.startswith("sqlite")
    connect_args: dict[str, Any] = {"check_same_thread": False, "timeout": 30} if is_sqlite else {}
    engine = create_engine(database_url, connect_args=connect_args, future=True)
    if is_sqlite:

        @event.listens_for(engine, "connect")
        def _pragmas(dbapi_connection: Any, _record: Any) -> None:
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.execute("PRAGMA busy_timeout=30000")
            cursor.execute("PRAGMA synchronous=NORMAL")
            # Deleted rows are overwritten, not just unlinked, so "delete" means gone.
            cursor.execute("PRAGMA secure_delete=ON")
            cursor.close()

    return engine


def scrub_deleted(engine: Engine) -> None:
    """After a deletion: fold the write-ahead log into the database and truncate it, so
    deleted content does not linger in the log file. Best effort while readers are active."""
    if engine.dialect.name == "sqlite":
        with engine.connect() as connection:
            connection.exec_driver_sql("PRAGMA wal_checkpoint(TRUNCATE)")


SessionFactory = sessionmaker[Session]


def make_session_factory(engine: Engine) -> SessionFactory:
    return sessionmaker(engine, expire_on_commit=False, future=True)


@contextmanager
def session_scope(factory: SessionFactory) -> Iterator[Session]:
    """One transaction: commit on success, roll back on any error."""
    session = factory()
    try:
        yield session
        session.commit()
    except BaseException:
        session.rollback()
        raise
    finally:
        session.close()
