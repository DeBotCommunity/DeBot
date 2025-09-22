import json
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, Any, List, Dict

from sqlalchemy import select, update, delete, asc, desc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload, joinedload

from userbot.utils.encrypt import encryption_manager
from userbot.db.models import Account, Session, Log, Module, AccountModule
from userbot.db.session import get_db

logger: logging.Logger = logging.getLogger(__name__)

# --- Account CRUD ---
async def add_account(db: AsyncSession, account_name: str, api_id: str, api_hash: str, lang_code: str, is_enabled: bool, device_model: str, system_version: str, app_version: str, user_telegram_id: int, access_hash: int, proxy_type: Optional[str] = None, proxy_ip: Optional[str] = None, proxy_port: Optional[int] = None, proxy_username: Optional[str] = None, proxy_password: Optional[str] = None) -> Optional[Account]:
    try:
        encrypted_proxy_user = encryption_manager.encrypt(proxy_username.encode('utf-8')) if proxy_username else None
        encrypted_proxy_pass = encryption_manager.encrypt(proxy_password.encode('utf-8')) if proxy_password else None
        new_account = Account(account_name=account_name, api_id=encryption_manager.encrypt(api_id.encode('utf-8')), api_hash=encryption_manager.encrypt(api_hash.encode('utf-8')), lang_code=lang_code, is_enabled=is_enabled, device_model=device_model, system_version=system_version, app_version=app_version, user_telegram_id=user_telegram_id, access_hash=access_hash, proxy_type=proxy_type, proxy_ip=proxy_ip, proxy_port=proxy_port, proxy_username=encrypted_proxy_user, proxy_password=encrypted_proxy_pass)
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

# --- Module Management ---
async def get_or_create_module(db: AsyncSession, name: str, path: str, git_url: str, desc: Optional[str], ver: Optional[str]) -> Module:
    result = await db.execute(select(Module).where(Module.module_name == name))
    module = result.scalars().first()
    if not module:
        module = Module(module_name=name, module_path=path, git_repo_url=git_url, description=desc, version=ver)
        db.add(module)
    else:
        module.module_path = path
        module.git_repo_url = git_url
        module.description = desc
        module.version = ver
    await db.flush()
    return module

async def get_module_by_name(db: AsyncSession, name: str) -> Optional[Module]:
    result = await db.execute(select(Module).where(Module.module_name == name))
    return result.scalars().first()

async def get_all_updatable_modules(db: AsyncSession) -> List[Module]:
    result = await db.execute(select(Module).where(Module.git_repo_url != None))
    return result.scalars().all()

async def link_module_to_account(db: AsyncSession, account_id: int, module_id: int, initial_config: Optional[bytes] = None) -> AccountModule:
    link = AccountModule(account_id=account_id, module_id=module_id, is_trusted=False, configuration=initial_config)
    db.add(link)
    await db.flush()
    return link

async def unlink_module_from_account(db: AsyncSession, account_id: int, module_id: int) -> bool:
    stmt = delete(AccountModule).where(AccountModule.account_id == account_id, AccountModule.module_id == module_id)
    result = await db.execute(stmt)
    return result.rowcount > 0

async def get_account_module_link(db: AsyncSession, account_id: int, module_id: int) -> Optional[AccountModule]:
    result = await db.execute(select(AccountModule).where(AccountModule.account_id == account_id, AccountModule.module_id == module_id))
    return result.scalars().first()

async def set_module_trust(db: AsyncSession, account_id: int, module_id: int, is_trusted: bool) -> bool:
    stmt = update(AccountModule).where(AccountModule.account_id == account_id, AccountModule.module_id == module_id).values(is_trusted=is_trusted)
    result = await db.execute(stmt)
    return result.rowcount > 0

async def get_module_config(db: AsyncSession, account_id: int, module_id: int) -> Optional[Dict[str, Any]]:
    link = await get_account_module_link(db, account_id, module_id)
    if not link or not link.configuration: return None
    try:
        decrypted_json = encryption_manager.decrypt(link.configuration)
        return json.loads(decrypted_json.decode('utf-8'))
    except Exception: return None

async def set_module_config(db: AsyncSession, account_id: int, module_id: int, config: Dict[str, Any]) -> bool:
    try:
        config_json = json.dumps(config).encode('utf-8')
        encrypted_config = encryption_manager.encrypt(config_json)
        stmt = update(AccountModule).where(AccountModule.account_id == account_id, AccountModule.module_id == module_id).values(configuration=encrypted_config)
        result = await db.execute(stmt)
        return result.rowcount > 0
    except Exception: return False

async def get_active_modules_for_account(db: AsyncSession, account_id: int) -> List[AccountModule]:
    stmt = select(AccountModule).where(AccountModule.account_id == account_id, AccountModule.is_active == True).options(joinedload(AccountModule.module))
    result = await db.execute(stmt)
    return result.scalars().all()

# --- Log Management ---
async def add_logs_bulk(db: AsyncSession, logs: List[Dict[str, Any]]) -> None:
    """
    Adds a batch of log entries to the database.

    Args:
        db (AsyncSession): The database session.
        logs (List[Dict[str, Any]]): A list of dictionaries, where each
            dictionary represents a log entry.
    """
    if not logs: return
    try:
        db.add_all([Log(**log_data) for log_data in logs])
        await db.flush()
    except Exception as e:
        # Fallback to console print if DB fails, to avoid losing logs entirely.
        print(f"CRITICAL: Error during bulk log insert: {e}")

async def get_logs_advanced(db: AsyncSession, mode: str, limit: int, level: Optional[str] = None, source: Optional[str] = None) -> List[Log]:
    stmt = select(Log)
    if level: stmt = stmt.where(Log.level == level.upper())
    if source: stmt = stmt.where(Log.module_name.ilike(f"%{source}%"))
    order = desc(Log.timestamp) if mode == "tail" else asc(Log.timestamp)
    stmt = stmt.order_by(order).limit(limit)
    result = await db.execute(stmt)
    logs = result.scalars().all()
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
