"""Alembic environment. The URL comes from the caller or from platform settings."""

from __future__ import annotations

from alembic import context
from sqlalchemy import create_engine

from protopitch.db.models import Base

config = context.config
target_metadata = Base.metadata


def _url() -> str:
    url = config.get_main_option("sqlalchemy.url")
    if url:
        return url
    from protopitch.settings import load_settings

    settings = load_settings()
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    return settings.database_url


def run_migrations() -> None:
    engine = create_engine(_url())
    with engine.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            render_as_batch=True,
            compare_type=True,
        )
        with context.begin_transaction():
            context.run_migrations()
    engine.dispose()


run_migrations()
