import asyncio
import sys
from pathlib import Path
import getpass
import argparse
import logging
from typing import Dict

# Add project root to sys.path
project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from telethon.sessions import StringSession
from telethon.errors import SessionPasswordNeededError

from userbot import TelegramClient, _generate_random_device
from userbot.src.db.session import get_db, initialize_database
import userbot.src.db_manager as db_manager
from userbot.src.encrypt import encryption_manager

# Configure logging to suppress noisy output from libraries
logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger('manage_account_cli')
logger.setLevel(logging.INFO)

async def add_account_logic(args):
    """
    Logic to add a new account with a full interactive Telethon login session.
    """
    logger.info(f"--- Adding new account: {args.name} ---")
    
    temp_client = None
    try:
        async with get_db() as db:
            if await db_manager.get_account(db, args.name):
                logger.error(f"Error: Account '{args.name}' already exists.")
                return

            api_id = input("Enter API ID: ").strip()
            api_hash = getpass.getpass("Enter API Hash: ").strip()

            if not api_id.isdigit() or not api_hash:
                logger.error("Error: API ID must be a number and API Hash cannot be empty.")
                return
            
            logger.info("Initializing temporary session to verify credentials...")
            temp_client = TelegramClient(StringSession(), int(api_id), api_hash)
            await temp_client.connect()

            if not await temp_client.is_user_authorized():
                phone_number = input("Session not found. Please enter your phone number (e.g., +1234567890): ").strip()
                await temp_client.send_code_request(phone_number)
                code = input("Please enter the code you received: ").strip()
                try:
                    await temp_client.sign_in(phone_number, code)
                except SessionPasswordNeededError:
                    two_fa_password = getpass.getpass("2FA Password required: ").strip()
                    await temp_client.sign_in(password=two_fa_password)

            me = await temp_client.get_me()
            user_id = me.id
            logger.info(f"Successfully logged in as {me.first_name} (ID: {user_id}).")

            existing_by_id = await db_manager.get_account_by_user_id(db, user_id)
            if existing_by_id:
                logger.error(f"Error: This Telegram account (ID: {user_id}) already exists in the database as '{existing_by_id.account_name}'.")
                return

            # --- New: Proxy Configuration ---
            proxy_details: Dict[str, Any] = {}
            if (input("Configure a proxy? (yes/no) [no]: ").lower() or 'no').startswith('y'):
                proxy_details['proxy_type'] = input("Proxy type (http, socks4, socks5): ").strip().lower()
                proxy_details['proxy_ip'] = input("Proxy IP address: ").strip()
                proxy_details['proxy_port'] = int(input("Proxy port: ").strip())
                proxy_details['proxy_username'] = input("Proxy username (optional, press Enter to skip): ").strip() or None
                proxy_details['proxy_password'] = getpass.getpass("Proxy password (optional, press Enter to skip): ").strip() or None

            # --- New: Device Configuration ---
            device_details: Dict[str, str]
            if (input("Set a custom device? (yes/no) [no]: ").lower() or 'no').startswith('y'):
                device_details = {
                    "device_model": input("Enter device model: ").strip(),
                    "system_version": input("Enter system version: ").strip(),
                    "app_version": input("Enter app version: ").strip()
                }
            else:
                device_details = _generate_random_device()
                logger.info(f"Generated random device: {device_details['device_model']}")
            
            lang_code = input(f"Enter language code (e.g., ru, en) [ru]: ").strip() or 'ru'
            is_enabled = (input("Enable this account now? (yes/no) [yes]: ").strip().lower() or 'yes').startswith('y')
            
            new_account = await db_manager.add_account(
                db, args.name, api_id, api_hash, lang_code, is_enabled,
                device_details['device_model'], device_details['system_version'], device_details['app_version'], user_id
            )
            # Proxy update is a separate step after account creation
            if new_account and proxy_details:
                account_to_update = await db_manager.get_account(db, args.name)
                account_to_update.proxy_type = proxy_details['proxy_type']
                account_to_update.proxy_ip = proxy_details['proxy_ip']
                account_to_update.proxy_port = proxy_details['proxy_port']
                if proxy_details['proxy_username']:
                    account_to_update.proxy_username = encryption_manager.encrypt(proxy_details['proxy_username'].encode())
                if proxy_details['proxy_password']:
                    account_to_update.proxy_password = encryption_manager.encrypt(proxy_details['proxy_password'].encode())

            if new_account:
                logger.info(f"\nSuccess! Account '{args.name}' was added. Restart the bot to activate the session.")
            else:
                logger.error("\nFailed to add the account to the database.")

    except Exception as e:
        logger.error(f"\nAn unexpected error occurred: {e}", exc_info=False)
    finally:
        if temp_client and temp_client.is_connected():
            await temp_client.disconnect()


async def toggle_account_logic(args):
    # Logic is unchanged
    pass

async def delete_account_logic(args):
    # Logic is unchanged
    pass

async def edit_account_logic(args):
    # Logic is unchanged
    pass

async def main():
    parser = argparse.ArgumentParser(description="DeBot Account Management CLI")
    # Parser setup is unchanged
    # ...
    # For brevity, only the add logic is shown as fully implemented
    parser_add = parser.add_subparsers().add_parser("add", help="Add a new account via interactive login")
    parser_add.add_argument("name", help="Unique name for the new account")
    parser_add.set_defaults(func=add_account_logic)
    
    args = parser.parse_args()
    
    await initialize_database()
    # Simplified for the example, a real implementation would dispatch correctly
    if hasattr(args, 'func'):
        await args.func(args)
    else:
        # Fallback for when no subcommand is given with the current simplified parser
        await add_account_logic(argparse.Namespace(name="default_add"))


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, EOFError):
        logger.info("\nOperation cancelled by user.")
    except Exception as e:
        logger.error(f"A critical error occurred: {e}", exc_info=True)
