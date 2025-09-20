import logging
from datetime import datetime, timezone
from typing import Optional, Any, List, Dict

from sqlalchemy import select, update, delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload

from userbot.src.encrypt import encryption_manager
from userbot.src.db.models import Account, Session, Module, AccountModule, Log, ModuleData

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
    user_telegram_id: Optional[int] = None
) -> Optional[Account]:
    """Adds a new account to the database with encrypted credentials."""
    try:
        new_account = Account(
            account_name=account_name,
            api_id=encryption_manager.encrypt(str(api_id).encode('utf-8')),
            api_hash=encryption_manager.encrypt(str(api_hash).encode('utf-8')),
            lang_code=lang_code,
            is_enabled=is_enabled,
            device_model=device_model,
            system_version=system_version,
            app_version=app_version,
            user_telegram_id=user_telegram_id
        )
        db.add(new_account)
        await db.flush()
        logger.info(f"Added account '{account_name}' with ID: {new_account.account_id}")
        return new_account
    except IntegrityError:
        logger.warning(f"Account with name '{account_name}' already exists.")
        await db.rollback()
        return None
    except Exception as e:
        logger.error(f"Error adding account '{account_name}': {e}")
        await db.rollback()
        return None

async def get_account(db: AsyncSession, account_name: str) -> Optional[Account]:
    """Retrieves an account by its name."""
    result = await db.execute(select(Account).where(Account.account_name == account_name))
    return result.scalars().first()
    
async def get_account_by_user_id(db: AsyncSession, user_id: int) -> Optional[Account]:
    """Retrieves an account by its Telegram User ID."""
    result = await db.execute(select(Account).where(Account.user_telegram_id == user_id))
    return result.scalars().first()

async def get_all_accounts(db: AsyncSession) -> List[Account]:
    """Retrieves all accounts from the database, with their sessions for status display."""
    result = await db.execute(select(Account).options(selectinload(Account.session)).order_by(Account.account_id))
    return result.scalars().all()

async def get_all_active_accounts(db: AsyncSession) -> List[Account]:
    """Retrieves all enabled accounts from the database."""
    result = await db.execute(select(Account).where(Account.is_enabled == True))
    return result.scalars().all()
    
async def delete_account(db: AsyncSession, account_name: str) -> bool:
    """Deletes an account by its name."""
    account = await get_account(db, account_name)
    if not account:
        return False
    await db.delete(account)
    await db.flush()
    return True

async def toggle_account_status(db: AsyncSession, account_name: str) -> Optional[bool]:
    """Toggles the is_enabled status of an account."""
    account = await get_account(db, account_name)
    if not account:
        return None
    account.is_enabled = not account.is_enabled
    await db.flush()
    return account.is_enabled
    
async def update_account_lang(db: AsyncSession, account_id: int, lang_code: str) -> bool:
    """Updates the language for a specific account."""
    stmt = update(Account).where(Account.account_id == account_id).values(lang_code=lang_code)
    result = await db.execute(stmt)
    return result.rowcount > 0

# --- Session CRUD ---
async def get_session(db: AsyncSession, account_id: int) -> Optional[Session]:
    """Retrieves a session for a given account and decrypts its auth key."""
    result = await db.execute(select(Session).where(Session.account_id == account_id))
    session = result.scalars().first()
    if session and session.auth_key_data:
        try:
            session.auth_key_data = encryption_manager.decrypt(session.auth_key_data)
        except Exception as e:
            logger.error(f"Failed to decrypt session auth_key for account {account_id}: {e}")
            return None
    return session

async def add_or_update_session(db: AsyncSession, **kwargs) -> Optional[Session]:
    """Adds or updates a session in the database, encrypting the auth key."""
    account_id = kwargs.get("account_id")
    if not account_id: return None
    
    result = await db.execute(select(Session).where(Session.account_id == account_id))
    session = result.scalars().first()
    
    if not session:
        session = Session(account_id=account_id)
        db.add(session)
        
    for key, value in kwargs.items():
        if key == "auth_key_data" and value is not None:
            value = encryption_manager.encrypt(value)
        setattr(session, key, value)
    
    session.last_used_at = datetime.now(timezone.utc)
    await db.flush()
    return session

async def delete_session(db: AsyncSession, account_id: int) -> bool:
    """Deletes a session from the database."""
    stmt = delete(Session).where(Session.account_id == account_id)
    result = await db.execute(stmt)
    await db.flush()
    return result.rowcount > 0

# --- Log CRUD ---
async def add_log(db: AsyncSession, level: str, message: str, account_id: Optional[int] = None, module_name: Optional[str] = None) -> Optional[Log]:
    """Adds a log entry to the database."""
    try:
        new_log = Log(
            level=level.upper(),
            message=message,
            account_id=account_id,
            module_name=module_name
        )
        db.add(new_log)
        await db.flush()
        return new_log
    except Exception as e:
        print(f"CRITICAL: Error adding log to database: {e}")
        return None

async def get_logs(db: AsyncSession, account_id: Optional[int] = None, limit: int = 100, level: Optional[str] = None) -> List[Log]:
    """Retrieves logs from the database with optional filters."""
    stmt = select(Log).order_by(Log.timestamp.desc()).limit(limit)
    if account_id is not None:
        stmt = stmt.where(Log.account_id == account_id)
    if level is not None:
        stmt = stmt.where(Log.level == level.upper())
    
    result = await db.execute(stmt)
    return result.scalars().all()
