from alembic import context
from sqlalchemy.ext.asyncio import create_async_engine
from flowforge.config import get_settings

settings = get_settings()


def run_migrations_online():
    connectable = create_async_engine(settings.database_url)
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=None)
        with context.begin_transaction():
            context.run_migrations()


run_migrations_online()
