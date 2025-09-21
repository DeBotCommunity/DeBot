import asyncio
import logging
import sys
from typing import Dict, Optional, Any, List

from faker import Faker
from telethon import TelegramClient as TelethonTelegramClient, events
from telethon.sessions import StringSession

from userbot.src.config import API_ID, API_HASH, LOG_LEVEL
from userbot.src.db.session import initialize_database, get_db
from userbot.src.db.models import Account
from userbot.src.db_session import DbSession
from userbot.src.encrypt import encryption_manager
import userbot.src.db_manager as db_manager
from userbot.src.log_handler import DBLogHandler
from userbot.src.locales import translator

# --- Basic Setup ---
logger: logging.Logger = logging.getLogger("userbot")
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

# --- Globals ---
ACTIVE_CLIENTS: Dict[int, "TelegramClient"] = {}
LOOP: asyncio.AbstractEventLoop = asyncio.get_event_loop()
FAKE: Faker = Faker()
GLOBAL_HELP_INFO: Dict[int, Dict[str, str]] = {}


# --- Core TelegramClient Class ---
class TelegramClient(TelethonTelegramClient):
    """
    Custom TelegramClient class with database interaction and localization methods.
    """
    def __init__(self, *args, **kwargs):
        """Initializes the custom Telegram client."""
        super().__init__(*args, **kwargs)
        self.lang_code: str = 'ru' # Default, will be overridden during init

    @property
    def current_account_id(self) -> Optional[int]:
        """
        Retrieves the account_id from the current DbSession.

        Returns:
            Optional[int]: The account ID if the session is a valid DbSession, otherwise None.
        """
        if hasattr(self, 'session') and isinstance(self.session, DbSession):
            return self.session.account_id
        return None
    
    async def get_string(self, key: str, module_name: Optional[str] = None, **kwargs) -> str:
        """
        Retrieves a translated string for the client's configured language.

        Args:
            key (str): The key of the string to retrieve.
            module_name (Optional[str]): The name of the module for module-specific strings.
            **kwargs: Arguments for string formatting.

        Returns:
            str: The translated and formatted string.
        """
        return translator.get_string(self.lang_code, key, module_name, **kwargs)

# --- Startup Logic ---
async def db_setup() -> None:
    """Initializes the database and attaches the DB logger."""
    if not API_ID or not API_HASH:
        logger.critical("API_ID or API_HASH is not set. Please run 'python3 -m scripts.setup'. Exiting.")
        sys.exit(1)
    
    try:
        await initialize_database()
    except Exception as e:
        logger.critical(f"Fatal error during database initialization: {e}", exc_info=True)
        sys.exit(1)
    
    db_handler: DBLogHandler = DBLogHandler()
    root_logger: logging.Logger = logging.getLogger()
    root_logger.setLevel(LOG_LEVEL)
    if not any(isinstance(h, DBLogHandler) for h in root_logger.handlers):
        root_logger.addHandler(db_handler)
    logger.info("Database schema checked and DB logger attached.")

async def start_individual_client(client: TelegramClient, account: Account) -> None:
    """Starts a client, loads its modules, and registers core handlers."""
    from userbot.__main__ import (
        load_account_modules, help_commands_handler, about_command_handler,
        add_account_handler, delete_account_handler,
        toggle_account_handler, list_accounts_handler, set_lang_handler
    )

    client.lang_code = account.lang_code
    account_name = account.account_name
    account_id = account.account_id

    logger.info(f"Attempting to start client for account: {account_name} (ID: {account_id})...")
    try:
        await client.start()
        if await client.is_user_authorized():
            logger.info(f"Client for account '{account_name}' (ID: {account_id}) is authorized.")
            GLOBAL_HELP_INFO[account_id] = {}
            
            client.add_event_handler(help_commands_handler, events.NewMessage(outgoing=True, pattern=r"^\.help$"))
            client.add_event_handler(about_command_handler, events.NewMessage(outgoing=True, pattern=r"^\.about$"))
            client.add_event_handler(list_accounts_handler, events.NewMessage(outgoing=True, pattern=r"^\.listaccs$"))
            client.add_event_handler(add_account_handler, events.NewMessage(outgoing=True, pattern=r"^\.addacc\s+([a-zA-Z0-9_]+)$"))
            client.add_event_handler(delete_account_handler, events.NewMessage(outgoing=True, pattern=r"^\.delacc\s+([a-zA-Z0-9_]+)$"))
            client.add_event_handler(toggle_account_handler, events.NewMessage(outgoing=True, pattern=r"^\.toggleacc\s+([a-zA-Z0-9_]+)$"))
            client.add_event_handler(set_lang_handler, events.NewMessage(outgoing=True, pattern=r"^\.setlang\s+([a-zA-Z]{2,5})$"))
            
            await load_account_modules(account_id, client, GLOBAL_HELP_INFO[account_id])
        else:
            logger.warning(f"Client for '{account_name}' started, but user is NOT authorized.")
    except Exception as e:
        logger.error(f"Error starting client for '{account_name}': {e}", exc_info=True)
        if account_id in ACTIVE_CLIENTS:
            del ACTIVE_CLIENTS[account_id]

async def manage_clients() -> None:
    """Fetches all enabled accounts from DB and starts them concurrently."""
    logger.info("Fetching all enabled accounts from the database...")
    all_accounts: List[Account] = []
    try:
        async with get_db() as db_session:
            all_accounts = await db_manager.get_all_active_accounts(db_session)
    except Exception as e:
        logger.critical(f"Could not fetch accounts from database. Is it running and configured correctly? Error: {e}")
        return

    if not all_accounts:
        logger.warning("No enabled accounts found in the database. No clients will be started.")
        logger.info("Use 'docker compose exec userbot python3 -m scripts.manage_account add <name>' to add your first account.")
        return

    logger.info(f"Found {len(all_accounts)} enabled accounts. Starting clients...")
    tasks = []
    for account in all_accounts:
        try:
            acc_api_id: str = encryption_manager.decrypt(account.api_id).decode()
            acc_api_hash: str = encryption_manager.decrypt(account.api_hash).decode()
        except Exception as e:
            logger.error(f"Could not decrypt credentials for account '{account.account_name}'. Skipping. Error: {e}")
            continue

        new_client: TelegramClient = TelegramClient(
            session=DbSession(account_id=account.account_id),
            api_id=int(acc_api_id),
            api_hash=acc_api_hash,
            device_model=account.device_model,
            system_version=account.system_version,
            app_version=account.app_version,
        )
        ACTIVE_CLIENTS[account.account_id] = new_client
        tasks.append(start_individual_client(new_client, account))
    
    await asyncio.gather(*tasks)
