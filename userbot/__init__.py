import argparse
import asyncio
import random
import string
import sys # Ensure sys is imported
import locale
import codecs
import os # For os.getenv in db_setup

import socks
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

# Global variable for the current account ID being used
CURRENT_ACCOUNT_ID = None
# --- End New Imports ---

if sys.getdefaultencoding() != 'utf-8':
    locale.setlocale(locale.LC_ALL, 'en_US.utf8')
    codecs.register_error("strict", codecs.ignore_errors)

# Generate FAKE device
FAKE = Faker()
sys_version = "".join(random.choice(string.ascii_uppercase) for _ in range(4))
device_model = random.choice(
    [
        FAKE.android_platform_token(),
        FAKE.ios_platform_token(),
        FAKE.linux_platform_token(),
        FAKE.windows_platform_token(),
    ]
)

# Parse arguments
PARSER = argparse.ArgumentParser(description="Параметры запуска")
PARSER.add_argument("-s", type=str, default="account", help="Путь к сессии (legacy, not used with DB session)")
PARSER.add_argument(
    "-p",
    nargs=5,
    type=str,
    default=None,
    help="Прокси (Proxy Type, IP, Port, username, password)",
)

ARGS = PARSER.parse_args()

# --- DB Setup and Account Management ---
# This block is placed before CLIENT instantiation.
# API_ID and API_HASH are expected to be loaded by "from userbot.src.config import *"

# Module-level 'global' declaration here is problematic and unnecessary.
# CURRENT_ACCOUNT_ID is already global by virtue of being defined at the module level.
# global CURRENT_ACCOUNT_ID # This line (original line 61) causes SyntaxError and should be removed.

async def db_setup_and_account_management():
    global CURRENT_ACCOUNT_ID, API_ID, API_HASH # Ensure access to global API_ID, API_HASH

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

    ACCOUNT_NAME = os.getenv("DEFAULT_ACCOUNT_NAME", "default_account")
    account = await get_account(account_name=ACCOUNT_NAME)
    
    if not account:
        # This check is crucial, API_ID and API_HASH must be available.
        if not API_ID or not API_HASH: 
            print("Error: API_ID and API_HASH are not set. Cannot create default account.", file=sys.stderr)
            sys.exit(1)

        # For DB storage (Step 4), API_ID/HASH stored as strings.
        # Encryption of these in DB is Step 5.
        # API_ID from config could be int or str, ensure str for DB.
        final_api_id_for_db = str(API_ID)
        final_api_hash_for_db = str(API_HASH) # API_HASH from config is likely already str.

        print(f"Creating default account '{ACCOUNT_NAME}'...")
        # add_account in db_manager expects api_id: str, api_hash: str
        # It returns the account_id (integer) or None
        account_id_val = await add_account(
            api_id=final_api_id_for_db,
            api_hash=final_api_hash_for_db,
            account_name=ACCOUNT_NAME
        )
        if not account_id_val: # add_account returns the ID now
            print(f"Error: Failed to create default account '{ACCOUNT_NAME}'. Exiting.", file=sys.stderr)
            sys.exit(1)
        CURRENT_ACCOUNT_ID = account_id_val
        print(f"Default account '{ACCOUNT_NAME}' created with ID: {CURRENT_ACCOUNT_ID}")
    else:
        CURRENT_ACCOUNT_ID = account['account_id'] # account is an asyncpg.Record
        print(f"Using existing account '{ACCOUNT_NAME}' with ID: {CURRENT_ACCOUNT_ID}")

_event_loop = asyncio.get_event_loop()
if _event_loop.is_running():
    asyncio.ensure_future(db_setup_and_account_management())
else:
    _event_loop.run_until_complete(db_setup_and_account_management())

# Ensure API_ID and API_HASH passed to TelegramClient are the original, non-encrypted values.
# These are already loaded from config.py.
if not API_ID or not API_HASH:
    print("CRITICAL: API_ID or API_HASH is missing after DB setup. Check .env and config.", file=sys.stderr)
    sys.exit(1)
# --- End DB Setup ---

# Help information for .help command
help_info = {
    "chat": """<b>❓ ᴋ᧐ʍᴀнды:</b>
            

<b>➖ 𝐂𝐡𝐚𝐭</b>""",
    "fun": """<b>➖ 𝐅𝐮𝐧</b>""",
    "tools": """<b>➖ 𝐓𝐨𝐨𝐥𝐬</b>
<code>.about</code> -> <i>о юзᴇᴩбоᴛᴇ</i>
<code>.addmod</code> -> <i>добᴀʙиᴛь ʍодуᴧь (ᴩᴇᴨᴧᴀᴇʍ нᴀ ɸᴀйᴧ)</i>
<code>.delmod</code> -> <i>удᴀᴧиᴛь ʍодуᴧь</i>""",
}

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
        pass   

    # The custom save() method that raised RuntimeError is REMOVED.

    async def __call__(self, *args, **kwargs):
        return await super().__call__(*args, **kwargs)

# The old "if API_ID is None: API_ID, API_HASH = preinstall()" block is removed
# as this logic is now part of db_setup_and_account_management or handled by config.py.

# --- TelegramClient Instantiation ---
if CURRENT_ACCOUNT_ID is None:
    print("Error: CURRENT_ACCOUNT_ID is not set. DB setup or account management failed. Trying to run setup again.", file=sys.stderr)
    # Attempt to run setup again if it somehow didn't complete or was skipped
    _event_loop.run_until_complete(db_setup_and_account_management()) # Use the same loop
    if CURRENT_ACCOUNT_ID is None:
            print("Critical Error: CURRENT_ACCOUNT_ID still not set after retry. Exiting.", file=sys.stderr)
            sys.exit(1)

db_session = DbSession(account_id=CURRENT_ACCOUNT_ID)
print(f"DbSession created for account_id: {CURRENT_ACCOUNT_ID}")

# Ensure API_ID is int and API_HASH is str for Telethon.
# API_ID and API_HASH from config.py should be correctly typed after loading from .env and decryption.
# Assuming config.py ensures API_ID is int, API_HASH is str. If not, convert here.
try:
    telethon_api_id = int(API_ID)
except ValueError:
    print(f"CRITICAL: API_ID ('{API_ID}') from config is not a valid integer. Exiting.", file=sys.stderr)
    sys.exit(1)
telethon_api_hash = str(API_HASH)


if ARGS.p is not None:
    PROXY_TYPE = None
    if ARGS.p[0].lower() == "http":
        PROXY_TYPE = socks.HTTP
    elif ARGS.p[0].lower() == "socks4":
        PROXY_TYPE = socks.SOCKS4
    elif ARGS.p[0].lower() == "socks5":
        PROXY_TYPE = socks.SOCKS5
    else:
        PROXY_TYPE = None # Explicitly set to None if no match

    # Validate PROXY_TYPE and Port
    if PROXY_TYPE is None:
        if ARGS.p[0]: # If a type was provided but it's invalid
            print(f"Error: Invalid proxy type '{ARGS.p[0]}'. Supported types are http, socks4, socks5. Proxy will not be used.", file=sys.stderr)
        else: # If type was empty (should not happen with nargs=5 if type is expected)
            print("Error: Proxy type is missing. Proxy will not be used.", file=sys.stderr)
        ARGS.p = None # Disable proxy

    if ARGS.p is not None: # Check if proxy is still enabled
        try:
            proxy_port = int(ARGS.p[2])
        except ValueError:
            print(f"Error: Invalid proxy port '{ARGS.p[2]}'. Port must be an integer. Proxy will not be used.", file=sys.stderr)
            ARGS.p = None # Disable proxy

    # Proceed with client initialization only if ARGS.p is still valid
    if ARGS.p is not None:
        CLIENT = TelegramClient(
            session=db_session,         # Use DbSession instance
            api_id=telethon_api_id,     # Use correctly typed API_ID
            api_hash=telethon_api_hash, # Use correctly typed API_HASH
            proxy=(
                PROXY_TYPE,
                ARGS.p[1],
                proxy_port, # Use the validated and converted port
                True,
                ARGS.p[3] if ARGS.p[3] != "0" else None,
                ARGS.p[4] if ARGS.p[4] != "0" else None,
            ),
            device_model=device_model,
            system_version=f"4.16.30-vxDEBOT{sys_version}",
        )
    else: # ARGS.p was invalidated by checks, or was None initially
        CLIENT = TelegramClient(
        session=db_session,         # Use DbSession instance
        api_id=telethon_api_id,     # Use correctly typed API_ID
        api_hash=telethon_api_hash, # Use correctly typed API_HASH
        device_model=device_model,
        system_version=f"4.16.30-vxDEBOT{sys_version}",
    )
# --- End TelegramClient Instantiation ---

async def start_client():
    """
    Asynchronously starts the client.
    """
    await CLIENT.start()
    if await CLIENT.is_user_authorized():
        print("Client started and user is authorized.")
        entity = await CLIENT.get_entity("https://t.me/DeBot_userbot")
        await CLIENT(JoinChannelRequest(entity))
    else:
        print("Client started, but user is NOT authorized. Manual login/authentication might be required.", file=sys.stderr)

client = CLIENT # Alias for other modules if they import client from here

# Run start_client() using asyncio
LOOP = _event_loop # Use the same loop that ran db_setup.

if LOOP.is_closed(): # Should ideally not happen in standard script execution
    print("Warning: Event loop was closed, re-getting for start_client.", file=sys.stderr)
    LOOP = asyncio.new_event_loop()
    asyncio.set_event_loop(LOOP)

try:
    LOOP.run_until_complete(start_client())
except Exception as e:
    print(f"Error during client execution: {e}", file=sys.stderr)
    # Consider closing DB pool here in case of error during client run
    # This needs access to the pool, e.g., via db_manager.DB_POOL
    # if not LOOP.is_closed() and userbot.src.db_manager.DB_POOL is not None:
    #    LOOP.run_until_complete(userbot.src.db_manager.close_db_pool())
finally:
    # Optional: Graceful shutdown of DB pool if the loop is being closed or script ends
    # print("Script ending. Consider closing DB pool if appropriate.")
    # if not LOOP.is_closed() and userbot.src.db_manager.DB_POOL is not None:
    #    LOOP.run_until_complete(userbot.src.db_manager.close_db_pool())
    pass
print("Userbot instance has finished running or encountered an error.")
