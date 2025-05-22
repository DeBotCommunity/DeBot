import argparse
import asyncio
import random
import string
import sys # Ensure sys is imported
import locale
import codecs
import os # For os.getenv in db_setup

from python_socks import ProxyType as PythonSocksProxyType
from faker import Faker
from telethon import TelegramClient as TelethonTelegramClient # Alias original client
from telethon.tl.functions.channels import JoinChannelRequest
from telethon.extensions import html

from userbot.src.config import * # API_ID, API_HASH are here
from userbot.src.preinstall import preinstall

# --- New Imports for DB Session ---
from userbot.src.db_manager import get_db_pool, initialize_database, add_account, get_account, DB_HOST, DB_PORT, DB_USER, DB_PASS, DB_NAME
from userbot.src.db_session import DbSession
# from userbot.src.encrypt import CryptoUtils # Keep if used for temporary API_ID/Hash encryption

# --- End New Imports ---

# CURRENT_ACCOUNT_ID is removed as we shift to multi-account management.
# API_ID and API_HASH will be used per client.

ACTIVE_CLIENTS = {} # For storing active client instances

if sys.getdefaultencoding() != 'utf-8':
    locale.setlocale(locale.LC_ALL, 'en_US.utf8')

# Generate FAKE device
FAKE = Faker() # Keep FAKE global as it's just a generator object

# sys_version and device_model will be generated per client inside manage_clients

# Parse arguments
PARSER = argparse.ArgumentParser(description="Параметры запуска")
PARSER.add_argument("-s", type=str, default="account", help="Путь к сессии (legacy, not used with DB session)")
# Remove the old -p argument for global proxy
# PARSER.add_argument(
#     "-p",
#     nargs=5,
#     type=str,
#     default=None,
#     help="Прокси (Proxy Type, IP, Port, username, password)",
# )
PARSER.add_argument(
    "--accounts",
    "-accs",
    nargs='+',
    default=[], # Default to an empty list, meaning no accounts specified unless via this arg
    help="Список имен аккаунтов для запуска (например: account1 account2)",
)

ARGS = PARSER.parse_args()

# --- DB Setup and Account Management ---
# This block is placed before CLIENT instantiation.
# API_ID and API_HASH are expected to be loaded by "from userbot.src.config import *"

async def db_setup_and_account_management():
    global API_ID, API_HASH # Ensure access to global API_ID, API_HASH

    # API_ID and API_HASH should be loaded from config.py or preinstall by this point.
    # config.py should attempt to load from .env. If they are still None, preinstall is the fallback.
    if API_ID is None or API_HASH is None:
        print("API_ID or API_HASH is None. Attempting preinstall to get credentials...", file=sys.stderr)
        _api_id_temp, _api_hash_temp = preinstall()
        if not _api_id_temp or not _api_hash_temp:
            print("Critical Error: API_ID and API_HASH could not be obtained via preinstall. Exiting.", file=sys.stderr)
            sys.exit(1)
        API_ID = _api_id_temp
        API_HASH = _api_hash_temp
        print("API_ID and API_HASH obtained via preinstall for DB setup.")

    # Initialize DB Pool
    # DB_HOST etc. are imported from db_manager, which should get them from config.py (os.getenv)
    await get_db_pool(
        host=DB_HOST, 
        port=DB_PORT, 
        user=DB_USER, 
        password=DB_PASS, 
        db_name=DB_NAME
    )
    await initialize_database()
    print("Database pool initialized and schema checked.")

    # Account creation/fetching logic is removed from here.
    # This function is now only for DB readiness.

_event_loop = asyncio.get_event_loop()
if _event_loop.is_running():
    asyncio.ensure_future(db_setup_and_account_management())
else:
    _event_loop.run_until_complete(db_setup_and_account_management())

# --- API Credential Check ---
# This check is vital before attempting to create any client.
if API_ID is None or API_HASH is None:
    print("API_ID or API_HASH is None. Attempting preinstall to get credentials...", file=sys.stderr)
    _api_id_temp, _api_hash_temp = preinstall()
    if not _api_id_temp or not _api_hash_temp:
        print("Critical Error: API_ID and API_HASH could not be obtained via preinstall. Exiting.", file=sys.stderr)
        sys.exit(1)
    API_ID = _api_id_temp
    API_HASH = _api_hash_temp
    print("API_ID and API_HASH obtained via preinstall for client setup.")
else:
    print("API_ID and API_HASH loaded from config.")

# --- Multi-Client Instantiation and Management ---
LOOP = _event_loop # Alias _event_loop to LOOP for clarity and potential use in __main__

# Lazy import for load_account_modules
_load_account_modules_func = None

# GLOBAL_HELP_INFO will store help dictionaries for each account_id
GLOBAL_HELP_INFO = {}

async def start_individual_client(client: TelethonTelegramClient, account_name: str, account_id: int):
    """
    Asynchronously starts an individual client, loads its modules,
    performs post-start actions, and handles authorization status.
    """
    global _load_account_modules_func, GLOBAL_HELP_INFO # Use GLOBAL_HELP_INFO

    if _load_account_modules_func is None:
        try:
            from userbot.__main__ import load_account_modules
            _load_account_modules_func = load_account_modules
        except ImportError as e:
            print(f"CRITICAL: Failed to import load_account_modules from userbot.__main__: {e}. Modules will not be loaded.", file=sys.stderr)
            # return # Potentially stop client

    print(f"Attempting to start client for account: {account_name} (ID: {account_id})...")
    try:
        await client.start()
        if await client.is_user_authorized():
            print(f"Client for account '{account_name}' (ID: {account_id}) started and user is authorized.")
            
            # Initialize help_info for this specific account
            help_for_this_account = {
                "chat": "<b>➖ Chat</b>",
                "fun": "<b>➖ Fun</b>",
                "tools": "<b>➖ Tools</b>" # Base tools category
            }
            # Add static commands to the 'tools' section for this account
            # Assuming convert_to_fancy_font is accessible or we simplify this part
            # For now, let's add them plainly.
            # from userbot.__main__ import convert_to_fancy_font # Would be circular if not careful
            # help_for_this_account["tools"] += f"\n<code>.about</code> -> <i>о юзᴇᴩбоᴛᴇ</i>"
            # help_for_this_account["tools"] += f"\n<code>.addmod</code> -> <i>добᴀʙиᴛь ʍодуᴧь</i>"
            # help_for_this_account["tools"] += f"\n<code>.delmod</code> -> <i>удᴀᴧиᴛь ʍодуᴧь</i>"
            # The above lines for static commands will be handled by help_command_handler to avoid import issues.
            # load_account_modules will populate based on dynamic modules.
            
            GLOBAL_HELP_INFO[account_id] = help_for_this_account

            if _load_account_modules_func:
                print(f"Loading modules for started client: {account_name} (ID: {account_id})")
                await _load_account_modules_func(account_id, client, help_for_this_account) # Pass the account-specific dict
            else:
                print(f"Module loading function not available for account {account_name}. Skipping module load.", file=sys.stderr)

            # Example post-start action: Join a channel
            try:
                entity = await client.get_entity("https://t.me/DeBot_userbot")
                await client(JoinChannelRequest(entity))
                print(f"Client for '{account_name}' joined DeBot_userbot channel.")
            except Exception as e:
                print(f"Error joining DeBot_userbot for account '{account_name}': {e}", file=sys.stderr)
        else:
            print(f"Client for account '{account_name}' (ID: {account_id}) started, but user is NOT authorized. Manual login required.", file=sys.stderr)
    except Exception as e:
        print(f"Error starting client or loading modules for account '{account_name}' (ID: {account_id}): {e}", file=sys.stderr)
        # Optionally remove from ACTIVE_CLIENTS if start fails significantly
        if account_id in ACTIVE_CLIENTS:
            del ACTIVE_CLIENTS[account_id]

async def manage_clients():
    global API_ID, API_HASH # Ensure access to global API_ID, API_HASH from config/preinstall
    global FAKE # Ensure FAKE is accessible

    if not ARGS.accounts:
        print("No accounts specified via --accounts or -accs. Userbot will not start any client sessions.")
        return

    print(f"Targeted accounts for startup: {', '.join(ARGS.accounts)}")

    for account_name in ARGS.accounts:
        print(f"Processing account: {account_name}...")
        account_details = await get_account(account_name=account_name)

        if account_details:
            account_id = account_details['account_id']
            
            # Use account-specific API credentials from the database
            acc_api_id = account_details.get('api_id')
            acc_api_hash = account_details.get('api_hash')

            if not acc_api_id or not acc_api_hash:
                print(f"Error: API ID or API Hash is missing in the database for account '{account_name}' (ID: {account_id}). Skipping client instantiation.", file=sys.stderr)
                continue # Skip this account

            try:
                telethon_api_id = int(acc_api_id)
            except ValueError:
                print(f"Error: API ID ('{acc_api_id}') for account '{account_name}' (ID: {account_id}) is not a valid integer. Skipping client instantiation.", file=sys.stderr)
                continue # Skip this account
            
            telethon_api_hash = str(acc_api_hash) # Ensure api_hash is a string

            db_session = DbSession(account_id=account_id)
            
            proxy_config = None
            if account_details.get('proxy_ip') and account_details.get('proxy_port'):
                proxy_type_str = account_details.get('proxy_type', '').lower()
                proxy_ip = account_details['proxy_ip']
                proxy_port = account_details['proxy_port']
                proxy_username = account_details.get('proxy_username') # Already decrypted
                proxy_password = account_details.get('proxy_password') # Already decrypted
                
                telethon_proxy_type = None
                if proxy_type_str == "http":
                    telethon_proxy_type = PythonSocksProxyType.HTTP
                elif proxy_type_str == "socks4":
                    telethon_proxy_type = PythonSocksProxyType.SOCKS4
                elif proxy_type_str == "socks5":
                    telethon_proxy_type = PythonSocksProxyType.SOCKS5
                
                if telethon_proxy_type:
                    proxy_config = (
                        telethon_proxy_type,
                        proxy_ip,
                        int(proxy_port),
                        True, # Rdns, default to True
                        proxy_username if proxy_username else None,
                        proxy_password if proxy_password else None,
                    )
                    print(f"Proxy configured for account '{account_name}': Type {proxy_type_str}")
                else:
                    print(f"Warning: Invalid or no proxy type ('{proxy_type_str}') specified for account '{account_name}'. No proxy will be used.", file=sys.stderr)
            
            # Generate unique device_model and system_version for each client
            current_sys_version_suffix = "".join(random.choice(string.ascii_uppercase) for _ in range(4))
            current_device_model = random.choice(
                [
                    FAKE.android_platform_token(),
                    FAKE.ios_platform_token(),
                    FAKE.linux_platform_token(),
                    FAKE.windows_platform_token(),
                ]
            )
            current_system_version = f"4.16.30-vxDEBOT{current_sys_version_suffix}"

            new_client = TelegramClient(
                session=db_session,
                api_id=telethon_api_id, # Using account-specific API_ID
                api_hash=telethon_api_hash, # Using account-specific API_HASH
                proxy=proxy_config,
                device_model=current_device_model, # Use unique device_model
                system_version=current_system_version, # Use unique system_version
            )
            
            ACTIVE_CLIENTS[account_id] = new_client
            print(f"TelegramClient instantiated for account '{account_name}' (ID: {account_id}). Scheduling start...")
            asyncio.create_task(start_individual_client(new_client, account_name, account_id))
        else:
            print(f"Error: Account '{account_name}' not found in the database. Skipping.", file=sys.stderr)

if _event_loop.is_running():
    asyncio.ensure_future(manage_clients())
else:
    _event_loop.run_until_complete(manage_clients())

# --- End Multi-Client Instantiation and Management ---

# Help information structure is now managed by GLOBAL_HELP_INFO per account.
# The old global help_info is removed.

# Use the aliased TelethonTelegramClient for subclassing
class TelegramClient(TelethonTelegramClient):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._parse_mode = html

    @property
    def parse_mode(self):
        return self._parse_mode

    @parse_mode.setter
    def parse_mode(self, mode):
        raise AttributeError("Default parse_mode is fixed to HTML and cannot be changed on the client instance. Set parse_mode per-call if needed.")

    # The custom save() method that raised RuntimeError is REMOVED.

    async def __call__(self, *args, **kwargs):
        return await super().__call__(*args, **kwargs)

# The old "if API_ID is None: API_ID, API_HASH = preinstall()" block is removed.
# Global API credentials check is done before manage_clients.

# The main event loop (LOOP / _event_loop) is now running manage_clients,
# which schedules individual client starts.

print("Userbot __init__ finished. Client management tasks scheduled if accounts were provided.")
# The script will continue running due to active tasks in the event loop if clients were started.
# If no accounts were specified, manage_clients returns and the script might exit soon after
# if no other long-running tasks are present.
