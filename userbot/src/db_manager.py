import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, Any, List, Dict

from sqlalchemy import select, update, delete, asc, desc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload

from userbot.src.encrypt import encryption_manager
from userbot.src.db.models import Account, Session, Log
from userbot.src.db.session import get_db

logger: logging.Logger = logging.getLogger(__name__)

# --- Account CRUD ---
async def add_account(
    db: AsyncSession,
    account_name: str,
    api_id: str,
    api_hash: str,
    lang_code: str,
    is_enabled: bool,
    device_model: str,
    system_version: str,
    app_version: str,
    user_telegram_id: int,
    access_hash: int,
    proxy_type: Optional[str] = None,
    proxy_ip: Optional[str] = None,
    proxy_port: Optional[int] = None,
    proxy_username: Optional[str] = None,
    proxy_password: Optional[str] = None
) -> Optional[Account]:
    try:
        encrypted_proxy_user = encryption_manager.encrypt(proxy_username.encode('utf-8')) if proxy_username else None
        encrypted_proxy_pass = encryption_manager.encrypt(proxy_password.encode('utf-8')) if proxy_password else None

        new_account = Account(
            account_name=account_name,
            api_id=encryption_manager.encrypt(api_id.encode('utf-8')),
            api_hash=encryption_manager.encrypt(api_hash.encode('utf-8')),
            lang_code=lang_code,
            is_enabled=is_enabled,
            device_model=device_model,
            system_version=system_version,
            app_version=app_version,
            user_telegram_id=user_telegram_id,
            access_hash=access_hash,
            proxy_type=proxy_type,
            proxy_ip=proxy_ip,
            proxy_port=proxy_port,
            proxy_username=encrypted_proxy_user,
            proxy_password=encrypted_proxy_pass
        )
        db.add(new_account)
        await db.flush()
        return new_account
    except IntegrityError:
        logger.warning(f"Account with name '{account_name}' or user_id '{user_telegram_id}' already exists.")
        await db.rollback()
        return None
    except Exception as e:
        logger.error(f"Error adding account '{account_name}': {e}")
        await db.rollback()
        raise

async def get_account(db: AsyncSession, account_name: str) -> Optional[Account]:
    result = await db.execute(select(Account).where(Account.account_name == account_name))
    return result.scalars().first()

async def get_account_by_user_id(db: AsyncSession, user_id: int) -> Optional[Account]:
    result = await db.execute(select(Account).where(Account.user_telegram_id == user_id))
    return result.scalars().first()

async def get_all_accounts(db: AsyncSession) -> List[Account]:
    result = await db.execute(select(Account).options(selectinload(Account.session)).order_by(Account.account_id))
    return result.scalars().all()

async def get_all_active_accounts(db: AsyncSession) -> List[Account]:
    result = await db.execute(select(Account).where(Account.is_enabled == True).options(selectinload(Account.session)))
    return result.scalars().all()
    
async def delete_account(db: AsyncSession, account_name: str) -> bool:
    account = await get_account(db, account_name)
    if not account: return False
    await db.delete(account)
    await db.flush()
    return True

async def toggle_account_status(db: AsyncSession, account_name: str) -> Optional[bool]:
    account = await get_account(db, account_name)
    if not account: return None
    account.is_enabled = not account.is_enabled
    await db.flush()
    return account.is_enabled
    
async def update_account_lang(db: AsyncSession, account_id: int, lang_code: str) -> bool:
    stmt = update(Account).where(Account.account_id == account_id).values(lang_code=lang_code)
    result = await db.execute(stmt)
    return result.rowcount > 0

# --- Session CRUD ---
async def get_session(db: AsyncSession, account_id: int) -> Optional[Session]:
    result = await db.execute(select(Session).where(Session.account_id == account_id))
    return result.scalars().first()

async def add_or_update_session(db: AsyncSession, account_id: int, session_file: bytes) -> Optional[Session]:
    if not account_id: return None
    
    result = await db.execute(select(Session).where(Session.account_id == account_id))
    session = result.scalars().first()
    
    encrypted_session_file = encryption_manager.encrypt(session_file)
    
    if not session:
        session = Session(account_id=account_id, session_file=encrypted_session_file)
        db.add(session)
    else:
        session.session_file = encrypted_session_file

    session.last_used_at = datetime.now(timezone.utc)
    await db.flush()
    return session

# --- Log Management ---
async def add_logs_bulk(db: AsyncSession, logs: List[Dict[str, Any]]) -> None:
    if not logs: return
    try:
        db.add_all([Log(**log_data) for log_data in logs])
        await db.flush()
    except Exception as e:
        print(f"CRITICAL: Error during bulk log insert: {e}")

async def get_logs_advanced(db: AsyncSession, mode: str, limit: int, level: Optional[str] = None, source: Optional[str] = None) -> List[Log]:
    """
    Retrieves logs from the database with advanced filtering and sorting.

    Args:
        db (AsyncSession): The database session.
        mode (str): 'head' for oldest logs, 'tail' for newest logs.
        limit (int): The maximum number of log entries to return.
        level (Optional[str]): Filter by log level (e.g., 'INFO', 'ERROR').
        source (Optional[str]): Filter by module name (case-insensitive).

    Returns:
        List[Log]: A list of Log objects matching the criteria.
    """
    stmt = select(Log)
    
    if level:
        stmt = stmt.where(Log.level == level.upper())
    if source:
        stmt = stmt.where(Log.module_name.ilike(f"%{source}%"))
    
    order = desc(Log.timestamp) if mode == "tail" else asc(Log.timestamp)
    stmt = stmt.order_by(order).limit(limit)
    
    result = await db.execute(stmt)
    logs = result.scalars().all()
    # If head mode, we need to reverse the results to show them in chronological order
    return list(reversed(logs)) if mode == "head" else logs

async def delete_old_logs(db: AsyncSession, days_to_keep: int) -> int:
    cutoff_date = datetime.now(timezone.utc) - timedelta(days=days_to_keep)
    stmt = delete(Log).where(Log.timestamp < cutoff_date)
    result = await db.execute(stmt)
    deleted_count: int = result.rowcount
    await db.flush()
    return deleted_count

async def purge_logs(db: AsyncSession) -> int:
    stmt = delete(Log)
    result = await db.execute(stmt)
    deleted_count: int = result.rowcount
    await db.flush()
    return deleted_count
