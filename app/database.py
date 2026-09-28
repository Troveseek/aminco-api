"""
Database session factory — async SQLAlchemy engine connecting to Supabase Postgres.
"""
from uuid import uuid4
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from typing import AsyncGenerator
from app.config import DATABASE_URL

engine = create_async_engine(
    DATABASE_URL,
    echo=False,           # Set to True during development if you want SQL logging
    pool_size=5,
    max_overflow=10,
    pool_pre_ping=True,   # Reconnect on dropped connections
    connect_args={
        "prepared_statement_name_func": lambda: f"__asyncpg_{uuid4().hex}__",
        "prepared_statement_cache_size": 0,
        "statement_cache_size": 0,
    },
)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
    autocommit=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency — provides an async DB session per request."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
