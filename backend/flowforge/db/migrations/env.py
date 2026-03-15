import asyncio
from alembic import context
from sqlalchemy.ext.asyncio import create_async_engine
from flowforge.config import get_settings
from flowforge.models import Base

settings = get_settings()
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode (generates SQL script)."""
    context.configure(
        url=settings.database_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode (connects to database)."""
    connectable = create_async_engine(settings.database_url)

    async def do_run() -> None:
        async with connectable.connect() as connection:
            await connection.run_sync(_run_migrations)

    asyncio.run(do_run())


def _run_migrations(connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
