import asyncio
from alembic import context
from sqlalchemy.ext.asyncio import create_async_engine
from flowforge.config import get_settings

settings = get_settings()

# TODO: import Base.metadata here in Task 2 when models are defined
# from flowforge.models import Base
# target_metadata = Base.metadata
target_metadata = None


def run_migrations_online():
    connectable = create_async_engine(settings.database_url)

    async def do_run():
        async with connectable.connect() as connection:
            await connection.run_sync(_run_migrations)

    asyncio.run(do_run())


def _run_migrations(connection):
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


run_migrations_online()
