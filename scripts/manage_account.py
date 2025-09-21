import asyncio
import sys
from pathlib import Path
import getpass
import argparse
import logging
import os
from typing import Dict, Optional

# Add project root to sys.path
project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from telethon.sessions import SQLiteSession
from telethon.errors import SessionPasswordNeededError

from userbot import TelegramClient, _generate_random_device
from userbot.src.db.session import get_db, initialize_database
import userbot.src.db_manager as db_manager
from userbot.src.encrypt import encryption_manager

logging.basicConfig(level=logging.WARNING, format='%(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('manage_account_cli')
logger.setLevel(logging.INFO)

async def add_account_logic(args: argparse.Namespace) -> None:
    """
    Handles the logic for adding a new account with a full interactive session.
    Allows for detailed configuration of device, proxy, and other settings.

    Args:
        args (argparse.Namespace): The command-line arguments, expecting `args.name`.
    """
    logger.info(f"--- Adding new account: {args.name} ---")
    
    session_file: str = f"temp_cli_{args.name}.session"
    temp_client: Optional[TelegramClient] = None
    try:
        async with get_db() as db:
            if await db_manager.get_account(db, args.name):
                logger.error(f"Error: Account '{args.name}' already exists.")
                return

            api_id: str = input("Enter API ID: ").strip()
            api_hash: str = getpass.getpass("Enter API Hash: ").strip()

            if not api_id.isdigit() or not api_hash:
                logger.error("Error: API ID must be a number and API Hash cannot be empty.")
                return
            
            logger.info("Initializing temporary session to verify credentials...")
            temp_client = TelegramClient(SQLiteSession(session_file), int(api_id), api_hash)
            await temp_client.connect()

            if not await temp_client.is_user_authorized():
                phone_number: str = input("Session not found. Please enter your phone number (e.g., +1234567890): ").strip()
                await temp_client.send_code_request(phone_number)
                code: str = input("Please enter the code you received: ").strip()
                try:
                    await temp_client.sign_in(phone_number, code)
                except SessionPasswordNeededError:
                    two_fa_password: str = getpass.getpass("2FA Password required: ").strip()
                    await temp_client.sign_in(password=two_fa_password)

            me = await temp_client.get_me(input_peer=True)
            user_id: int = me.user_id
            access_hash: int = me.access_hash
            logger.info(f"Successfully logged in as user ID: {user_id}.")

            await temp_client.disconnect() # Disconnect to ensure session file is fully written

            existing_by_id = await db_manager.get_account_by_user_id(db, user_id)
            if existing_by_id:
                logger.error(f"Error: This Telegram account (ID: {user_id}) already exists as '{existing_by_id.account_name}'.")
                return

            # --- Interactive Configuration ---
            print("\n--- Account Configuration ---")
            lang_code: str = input(f"Enter language code (e.g., ru, en) [ru]: ").strip() or 'ru'
            is_enabled: bool = (input("Enable this account now? (yes/no) [yes]: ").strip().lower() or 'yes').startswith('y')

            # Device Configuration
            if (input("Configure custom device details? (yes/no) [no]: ").strip().lower()).startswith('y'):
                device_model: str = input("Enter device model: ").strip()
                system_version: str = input("Enter system version: ").strip()
                app_version: str = input("Enter app version: ").strip()
            else:
                device_details: Dict[str, str] = _generate_random_device()
                device_model = device_details['device_model']
                system_version = device_details['system_version']
                app_version = device_details['app_version']
                logger.info("Generated random device details.")

            # Proxy Configuration
            proxy_type: Optional[str] = None
            proxy_ip: Optional[str] = None
            proxy_port: Optional[int] = None
            proxy_username: Optional[str] = None
            proxy_password: Optional[str] = None
            if (input("Configure a proxy for this account? (yes/no) [no]: ").strip().lower()).startswith('y'):
                proxy_type_input = ""
                while proxy_type_input not in ["http", "socks4", "socks5"]:
                    proxy_type_input = input("Enter proxy type (http, socks4, socks5): ").strip().lower()
                proxy_type = proxy_type_input
                proxy_ip = input("Enter proxy IP address: ").strip()
                proxy_port_str = ""
                while not proxy_port_str.isdigit():
                    proxy_port_str = input("Enter proxy port: ").strip()
                proxy_port = int(proxy_port_str)
                if (input("Does the proxy require authentication? (yes/no) [no]: ").strip().lower()).startswith('y'):
                    proxy_username = input("Enter proxy username: ").strip()
                    proxy_password = getpass.getpass("Enter proxy password: ").strip()

            logger.info("\nSaving account to the database...")
            new_account = await db_manager.add_account(
                db,
                account_name=args.name,
                api_id=api_id,
                api_hash=api_hash,
                lang_code=lang_code,
                is_enabled=is_enabled,
                device_model=device_model,
                system_version=system_version,
                app_version=app_version,
                user_telegram_id=user_id,
                access_hash=access_hash,
                proxy_type=proxy_type,
                proxy_ip=proxy_ip,
                proxy_port=proxy_port,
                proxy_username=proxy_username,
                proxy_password=proxy_password
            )
            
            if not new_account:
                logger.error("\nFailed to add the account to the database.")
                return

            # Now extract session from file and save to DB
            logger.info("Extracting session data and saving to the database...")
            reader_session = SQLiteSession(session_file)
            reader_session.load()
            
            update_state = reader_session.get_update_state(0)
            pts, qts, date_ts, seq, _ = (None, None, None, None, None)
            if update_state:
                pts, qts, date_ts, seq, _ = update_state

            await db_manager.add_or_update_session(
                db,
                account_id=new_account.account_id,
                dc_id=reader_session.dc_id,
                server_address=reader_session.server_address,
                port=reader_session.port,
                auth_key_data=reader_session.auth_key.key,
                takeout_id=reader_session.takeout_id,
                pts=pts, qts=qts, date=date_ts, seq=seq
            )
            
            logger.info(f"\nSuccess! Account '{args.name}' was added. Restart the bot to activate.")

    except Exception as e:
        logger.error(f"\nAn unexpected error occurred: {e}", exc_info=True)
    finally:
        if temp_client and temp_client.is_connected():
            await temp_client.disconnect()
        if os.path.exists(session_file):
            os.remove(session_file)
            logger.info(f"Cleaned up temporary session file: {session_file}")


async def edit_account_logic(args: argparse.Namespace) -> None:
    """Logic to edit an account's properties."""
    logger.info(f"--- Editing account: {args.name} ---")
    async with get_db() as db:
        account = await db_manager.get_account(db, args.name)
        if not account:
            logger.error(f"Error: Account '{args.name}' not found.")
            return

        updated_fields = []
        # ... (full implementation as in previous correct answer)
        
        if updated_fields:
            logger.info("Success! Fields updated.")
        else:
            logger.info("No changes specified.")

# ... (other logic functions like toggle, delete)

async def main() -> None:
    """The main entry point for the CLI script."""
    parser = argparse.ArgumentParser(description="DeBot Account Management CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    parser_add = subparsers.add_parser("add", help="Add a new account via interactive login")
    parser_add.add_argument("name", help="Unique name for the new account")
    parser_add.set_defaults(func=add_account_logic)
    
    # ... (full parser setup as in previous correct answer)

    args: argparse.Namespace = parser.parse_args()
    
    await initialize_database()
    if hasattr(args, 'func'):
        await args.func(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, EOFError):
        logger.info("\nOperation cancelled by user.")
