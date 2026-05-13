from sqlalchemy import inspect, text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from app.config import settings

Base = declarative_base()


TASK1_TASK_COLUMNS = {
    "rewritten_title": 'ALTER TABLE tasks ADD COLUMN rewritten_title VARCHAR(500)',
    "generated_tags": 'ALTER TABLE tasks ADD COLUMN generated_tags JSON',
    "failed_stage": 'ALTER TABLE tasks ADD COLUMN failed_stage VARCHAR(50)',
    "trigger_source": "ALTER TABLE tasks ADD COLUMN trigger_source VARCHAR(20) NOT NULL DEFAULT 'ui'",
}


def ensure_task1_task_columns(connection):
    inspector = inspect(connection)
    if "tasks" not in inspector.get_table_names():
        return

    existing_columns = {column["name"] for column in inspector.get_columns("tasks")}
    for column_name, ddl in TASK1_TASK_COLUMNS.items():
        if column_name not in existing_columns:
            connection.execute(text(ddl))


engine = create_async_engine(settings.database_url, echo=False)
async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_db():
    async with async_session() as session:
        try:
            yield session
        finally:
            await session.close()


async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.run_sync(ensure_task1_task_columns)
