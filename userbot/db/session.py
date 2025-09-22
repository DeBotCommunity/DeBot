import logging
import asyncio
import sys
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.exc import SQLAlchemyError

from userbot.core.config import (
    DB_TYPE, DB_HOST, DB_PORT, DB_USER, DB_PASS, DB_NAME,
    DB_CONN_RETRIES, DB_CONN_RETRY_DELAY
)
from userbot.db.models import Base

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
    Connects to the database and creates all tables based on the SQLAlchemy models.
    Includes a retry mechanism to handle database startup delays.
    """
    for attempt in range(DB_CONN_RETRIES):
        try:
            async with async_engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            logger.info("Database schema initialization check complete.")
            return  # Success, exit the function
        except (ConnectionRefusedError, OSError, asyncio.TimeoutError) as e:
            if attempt < DB_CONN_RETRIES - 1:
                logger.warning(
                    f"Database connection failed (attempt {attempt + 1}/{DB_CONN_RETRIES}): {e}. "
                    f"Retrying in {DB_CONN_RETRY_DELAY} seconds..."
                )
                await asyncio.sleep(DB_CONN_RETRY_DELAY)
            else:
                logger.critical(
                    f"Could not connect to the database after {DB_CONN_RETRIES} attempts. "
                    "Please ensure the database is running and the .env file is configured correctly."
                )
                raise  # Re-raise the final exception to stop the application
    
    # This part should not be reachable if all retries fail, but as a safeguard:
    logger.critical("Exhausted all retries to connect to the database. Exiting.")
    sys.exit(1)


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
