from __future__ import annotations

from collections.abc import AsyncIterator
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from core.config import settings


class Base(DeclarativeBase):
    pass


def _ensure_sqlite_directory(database_url: str) -> None:
    sqlite_prefix = "sqlite+aiosqlite:///"
    if not database_url.startswith(sqlite_prefix):
        return
    raw_path = database_url.removeprefix(sqlite_prefix)
    if raw_path == ":memory:":
        return
    Path(raw_path).expanduser().resolve().parent.mkdir(parents=True, exist_ok=True)


_ensure_sqlite_directory(settings.database_url)

engine: AsyncEngine = create_async_engine(
    settings.database_url,
    echo=False,
    future=True,
    connect_args={"timeout": 30},
)

SessionFactory = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


async def get_session() -> AsyncIterator[AsyncSession]:
    async with SessionFactory() as session:
        yield session


async def init_database() -> None:
    from core.models import AccessRequest, SearchTask, User

    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
        await _apply_sqlite_compatibility_migrations(connection)


async def _apply_sqlite_compatibility_migrations(connection: AsyncSession) -> None:
    if not settings.database_url.startswith("sqlite+aiosqlite:///"):
        return

    await _ensure_column(connection, "users", "role", "VARCHAR(16) DEFAULT 'basic'")
    await _ensure_column(connection, "users", "is_active", "BOOLEAN DEFAULT 1")
    await _ensure_column(connection, "users", "is_yht_active", "BOOLEAN DEFAULT 0")
    await _ensure_column(connection, "access_requests", "user_id", "INTEGER")
    await _ensure_column(connection, "access_requests", "username", "VARCHAR(255)")
    await _ensure_column(connection, "access_requests", "first_name", "VARCHAR(255)")
    await _ensure_column(connection, "access_requests", "last_name", "VARCHAR(255)")
    await _ensure_column(connection, "access_requests", "status", "VARCHAR(16) DEFAULT 'pending'")
    await _ensure_column(connection, "access_requests", "is_notified", "BOOLEAN DEFAULT 0")
    await _ensure_column(connection, "access_requests", "requested_at", "DATETIME")
    await _ensure_column(connection, "access_requests", "resolved_at", "DATETIME")
    await _ensure_column(connection, "search_tasks", "train_id", "INTEGER")
    await _ensure_column(connection, "search_tasks", "train_car_id", "INTEGER")
    await _ensure_column(connection, "search_tasks", "allocation_id", "VARCHAR(64)")
    await _ensure_column(connection, "search_tasks", "seat_number", "VARCHAR(32)")
    await _ensure_column(connection, "search_tasks", "hold_attempt_count", "INTEGER DEFAULT 0")
    await _ensure_column(connection, "search_tasks", "hold_expires_at", "DATETIME")
    await _ensure_column(connection, "search_tasks", "last_economy_count", "INTEGER")
    await _ensure_column(connection, "search_tasks", "last_business_count", "INTEGER")


async def _ensure_column(connection, table_name: str, column_name: str, column_sql: str) -> None:
    result = await connection.execute(text("PRAGMA table_info(%s)" % table_name))
    column_names = {row[1] for row in result.fetchall()}
    if column_name in column_names:
        return
    await connection.execute(
        text("ALTER TABLE %s ADD COLUMN %s %s" % (table_name, column_name, column_sql))
    )
