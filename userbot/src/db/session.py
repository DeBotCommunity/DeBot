import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.exc import SQLAlchemyError

from userbot.src.config import DB_TYPE, DB_HOST, DB_PORT, DB_USER, DB_PASS, DB_NAME
from userbot.src.db.models import Base

logger: logging.Logger = logging.getLogger(__name__)

# Currently only postgresql is supported via asyncpg
DATABASE_URL: str = f"{DB_TYPE}+asyncpg://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

try:
    async_engine = create_async_engine(DATABASE_URL, echo=False)
    AsyncSessionLocal = async_sessionmaker(
        autocommit=False,
        autoflush=False,
        bind=async_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
except ImportError:
    logger.critical("asyncpg driver not installed. Please run 'pip install asyncpg'")
    raise
except Exception as e:
    logger.critical(f"Failed to create database engine: {e}")
    raise

async def initialize_database() -> None:
    """
    Creates all tables in the database based on the SQLAlchemy models.
    """
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database schema initialization check complete.")

@asynccontextmanager
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Provides a transactional scope around a series of operations.

    Yields:
        AsyncSession: The database session.
    """
    session: AsyncSession = AsyncSessionLocal()
    try:
        yield session
        await session.commit()
    except SQLAlchemyError as e:
        await session.rollback()
        logger.error(f"Database session error: {e}", exc_info=True)
        raise
    finally:
        await session.close()
