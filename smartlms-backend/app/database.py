"""
Smart LMS Backend - Database Connection
Async SQLAlchemy engine for Neon DB (PostgreSQL)
"""

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from app.config import settings


# Async engine setup - Diverge based on dialect
if "sqlite" in settings.DATABASE_URL:
    engine = create_async_engine(
        settings.DATABASE_URL,
        echo=settings.SQL_ECHO,
        connect_args={"check_same_thread": False},
    )

    # Enable SQLite foreign key enforcement
    from sqlalchemy import event
    @event.listens_for(engine.sync_engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()
else:
    engine = create_async_engine(
        settings.DATABASE_URL,
        echo=settings.SQL_ECHO,
        pool_pre_ping=True,
        pool_size=settings.DB_POOL_SIZE,
        max_overflow=settings.DB_MAX_OVERFLOW,
        pool_recycle=settings.DB_POOL_RECYCLE_SECONDS,
        connect_args={
            "timeout": settings.DB_CONNECT_TIMEOUT_SECONDS,
            "command_timeout": settings.DB_COMMAND_TIMEOUT_SECONDS,
            "server_settings": {
                "application_name": "smartlms-backend",
            },
        },
    )

# Async session factory
async_session = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    """Base class for all ORM models"""
    pass


async def get_db():
    """Dependency: yield an async database session"""
    async with async_session() as session:
        try:
            yield session
        finally:
            await session.close()


async def create_tables():
    """Create all tables (for development — use Alembic in production)"""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def drop_tables():
    """Drop all tables (DANGEROUS - development only)"""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


from datetime import datetime, timezone, timedelta

def get_ist_now() -> datetime:
    """Helper: get current time in Indian Standard Time (UTC+5:30)"""
    ist = timezone(timedelta(hours=5, minutes=30))
    return datetime.now(ist)
