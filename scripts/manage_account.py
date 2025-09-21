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

            me = await temp_client.get_me(input_peer=True)
            user_id = me.user_id
            access_hash = me.access_hash
            logger.info(f"Successfully logged in as user ID: {user_id}.")

            existing_by_id = await db_manager.get_account_by_user_id(db, user_id)
            if existing_by_id:
                logger.error(f"Error: This Telegram account (ID: {user_id}) already exists as '{existing_by_id.account_name}'.")
                return

            device_details = _generate_random_device()
            lang_code = input(f"Enter language code (e.g., ru, en) [ru]: ").strip() or 'ru'
            is_enabled = (input("Enable this account now? (yes/no) [yes]: ").strip().lower() or 'yes').startswith('y')
            
            new_account = await db_manager.add_account(
                db, args.name, api_id, api_hash, lang_code, is_enabled,
                device_details['device_model'], device_details['system_version'], device_details['app_version'], 
                user_id, access_hash
            )
            
            if new_account:
                logger.info(f"\nSuccess! Account '{args.name}' was added. Restart the bot to activate.")
            else:
                logger.error("\nFailed to add the account to the database.")

    except Exception as e:
        logger.error(f"\nAn unexpected error occurred: {e}", exc_info=False)
    finally:
        if temp_client and temp_client.is_connected():
            await temp_client.disconnect()


async def edit_account_logic(args):
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

async def main():
    parser = argparse.ArgumentParser(description="DeBot Account Management CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    parser_add = subparsers.add_parser("add", help="Add a new account via interactive login")
    parser_add.add_argument("name", help="Unique name for the new account")
    parser_add.set_defaults(func=add_account_logic)
    
    # ... (full parser setup as in previous correct answer)

    args = parser.parse_args()
    
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
