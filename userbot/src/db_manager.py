import logging
from datetime import datetime, timezone, timedelta
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
        logger.warning(f"Account with name '{account_name}' or user_id '{user_telegram_id}' already exists.")
        await db.rollback()
        return None
    except Exception as e:
        logger.error(f"Error adding account '{account_name}': {e}")
        await db.rollback()
        raise

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
    if not account: return False
    await db.delete(account)
    await db.flush()
    return True

async def toggle_account_status(db: AsyncSession, account_name: str) -> Optional[bool]:
    """Toggles the is_enabled status of an account."""
    account = await get_account(db, account_name)
    if not account: return None
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
    
    # Use a raw select to avoid decryption/re-encryption cycle of get_session
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

# --- Module Management ---
async def get_module(db: AsyncSession, module_name: str) -> Optional[Module]:
    """Retrieves a module by its name."""
    result = await db.execute(select(Module).where(Module.module_name == module_name))
    return result.scalars().first()

async def get_all_modules(db: AsyncSession) -> List[Module]:
    """Retrieves all modules from the database."""
    result = await db.execute(select(Module))
    return result.scalars().all()

async def add_module(db: AsyncSession, module_name: str, module_path: str) -> Optional[Module]:
    """Adds a new module or returns the existing one."""
    module = await get_module(db, module_name)
    if module:
        module.module_path = module_path
        await db.flush()
        return module
    new_module = Module(module_name=module_name, module_path=module_path)
    db.add(new_module)
    await db.flush()
    return new_module

async def get_account_module(db: AsyncSession, account_id: int, module_id: int) -> Optional[AccountModule]:
    """Retrieves the link between an account and a module."""
    result = await db.execute(
        select(AccountModule).where(AccountModule.account_id == account_id, AccountModule.module_id == module_id)
    )
    return result.scalars().first()

async def link_module_to_account(db: AsyncSession, account_id: int, module_id: int, is_active: bool, configuration: Optional[Dict[str, Any]]) -> Optional[AccountModule]:
    """Links a module to an account or updates the existing link."""
    link = await get_account_module(db, account_id, module_id)
    if not link:
        link = AccountModule(account_id=account_id, module_id=module_id)
        db.add(link)
    link.is_active = is_active
    if configuration is not None:
        link.configuration = configuration
    await db.flush()
    return link

async def get_active_modules_for_account(db: AsyncSession, account_id: int) -> List[Dict[str, Any]]:
    """Retrieves all active modules for a specific account."""
    stmt = (
        select(Module, AccountModule.is_trusted, AccountModule.configuration)
        .join(AccountModule, Module.module_id == AccountModule.module_id)
        .where(AccountModule.account_id == account_id, AccountModule.is_active == True)
    )
    results = await db.execute(stmt)
    return [
        {
            'module': module,
            'is_trusted': is_trusted,
            'configuration': configuration
        }
        for module, is_trusted, configuration in results.all()
    ]

async def unlink_module_from_account(db: AsyncSession, account_id: int, module_id: int) -> bool:
    """Unlinks a module from an account."""
    stmt = delete(AccountModule).where(AccountModule.account_id == account_id, AccountModule.module_id == module_id)
    result = await db.execute(stmt)
    return result.rowcount > 0

async def set_module_trust_status(db: AsyncSession, account_id: int, module_id: int, is_trusted: bool) -> bool:
    """Sets the trust status for a module link."""
    link = await get_account_module(db, account_id, module_id)
    if not link: return False
    link.is_trusted = is_trusted
    await db.flush()
    return True

async def update_module_config(db: AsyncSession, account_id: int, module_id: int, config_key: str, config_value: Any) -> bool:
    """Updates a single key in a module's JSONB configuration."""
    link = await get_account_module(db, account_id, module_id)
    if not link: return False
    if link.configuration is None:
        link.configuration = {}
    new_config = dict(link.configuration)
    new_config[config_key] = config_value
    link.configuration = new_config
    await db.flush()
    return True

# --- Log Management ---
async def add_logs_bulk(db: AsyncSession, logs: List[Dict[str, Any]]) -> None:
    """Adds a batch of log entries to the database."""
    if not logs: return
    try:
        db.add_all([Log(**log_data) for log_data in logs])
        await db.flush()
    except Exception as e:
        print(f"CRITICAL: Error during bulk log insert: {e}")

async def get_logs_filtered(db: AsyncSession, limit: int, level: Optional[str] = None, source: Optional[str] = None) -> List[Log]:
    """Retrieves logs from the database with optional filters."""
    stmt = select(Log).order_by(Log.timestamp.desc()).limit(limit)
    if level:
        stmt = stmt.where(Log.level == level.upper())
    if source:
        stmt = stmt.where(Log.module_name.ilike(f"%{source}%"))
    result = await db.execute(stmt)
    return result.scalars().all()

async def delete_old_logs(db: AsyncSession, days_to_keep: int) -> int:
    """Deletes log entries older than a specified number of days."""
    cutoff_date = datetime.now(timezone.utc) - timedelta(days=days_to_keep)
    stmt = delete(Log).where(Log.timestamp < cutoff_date)
    result = await db.execute(stmt)
    return result.rowcount

async def purge_logs(db: AsyncSession) -> int:
    """Deletes all log entries from the database."""
    stmt = delete(Log)
    result = await db.execute(stmt)
    return result.rowcount
