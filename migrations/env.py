import os
from alembic import context
from sqlalchemy import create_engine, pool, text

DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql://pptagent:pptagent_local@localhost:5432/pptagent",
)

config = context.config


def run_migrations_online() -> None:
    url = config.get_main_option("sqlalchemy.url") or DATABASE_URL
    engine = create_engine(url, poolclass=pool.NullPool)
    with engine.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=None,
            compare_type=True,
        )
        with context.begin_transaction():
            context.run_migrations()


run_migrations_online()
