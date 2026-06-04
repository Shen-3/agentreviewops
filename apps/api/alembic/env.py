from __future__ import annotations

import os
from logging.config import fileConfig

from sqlalchemy import Column, MetaData, String, Table, engine_from_config, pool, text

from agentreview_api.db import Base
from alembic import context

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata
ALEMBIC_VERSION_COLUMN_LENGTH = 255


def _database_url() -> str:
    return os.environ.get("AGENTREVIEW_DATABASE_URL") or config.get_main_option("sqlalchemy.url")


def _ensure_version_table_width(connection) -> None:
    """Keep Alembic revision IDs portable across stricter databases."""
    metadata = MetaData()
    version_table = Table(
        "alembic_version",
        metadata,
        Column("version_num", String(ALEMBIC_VERSION_COLUMN_LENGTH), primary_key=True),
    )
    version_table.create(connection, checkfirst=True)

    if connection.dialect.name == "postgresql":
        connection.execute(
            text(f"ALTER TABLE alembic_version ALTER COLUMN version_num TYPE VARCHAR({ALEMBIC_VERSION_COLUMN_LENGTH})")
        )


def run_migrations_offline() -> None:
    context.configure(
        url=_database_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    configuration = config.get_section(config.config_ini_section, {})
    configuration["sqlalchemy.url"] = _database_url()
    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        with connection.begin():
            _ensure_version_table_width(connection)
        context.configure(connection=connection, target_metadata=target_metadata)

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
