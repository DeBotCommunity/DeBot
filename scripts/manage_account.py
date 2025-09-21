import asyncio
import sys
from pathlib import Path
import getpass
import argparse
import logging
import os
from typing import Dict, Optional, Coroutine, Any, Callable

# Add project root to sys.path
project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from telethon.sessions import SQLiteSession
from telethon.errors import SessionPasswordNeededError
from sqlalchemy.ext.asyncio import AsyncSession

from userbot import TelegramClient, _generate_random_device
from userbot.src.db.session import get_db, initialize_database
import userbot.src.db_manager as db_manager
from userbot.src.encrypt import encryption_manager
from userbot.src.db.models import Account

logging.basicConfig(level=logging.WARNING, format='%(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('manage_account_cli')
logger.setLevel(logging.INFO)

async def add_account_logic(args: argparse.Namespace) -> None:
    # ... (Implementation from previous correct response remains unchanged)
    logger.info(f"--- Adding new account: {args.name} ---")
    
    session_file_path: str = f"temp_cli_{args.name}.session"
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
            temp_client = TelegramClient(SQLiteSession(session_file_path), int(api_id), api_hash)
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

            await temp_client.disconnect()

            existing_by_id = await db_manager.get_account_by_user_id(db, user_id)
            if existing_by_id:
                logger.error(f"Error: This Telegram account (ID: {user_id}) already exists as '{existing_by_id.account_name}'.")
                return

            print("\n--- Account Configuration ---")
            lang_code: str = input(f"Enter language code (e.g., ru, en) [ru]: ").strip() or 'ru'
            is_enabled: bool = (input("Enable this account now? (yes/no) [yes]: ").strip().lower() or 'yes').startswith('y')

            if (input("Configure custom device details? (yes/no) [no]: ").strip().lower()).startswith('y'):
                device_model: str = input("Enter device model: ").strip()
                system_version: str = input("Enter system version: ").strip()
                app_version: str = input("Enter app version: ").strip()
            else:
                device_details: Dict[str, str] = _generate_random_device()
                device_model, system_version, app_version = device_details.values()
                logger.info("Generated random device details.")

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
            new_account = await db_manager.add_account(db, args.name, api_id, api_hash, lang_code, is_enabled, device_model, system_version, app_version, user_id, access_hash, proxy_type, proxy_ip, proxy_port, proxy_username, proxy_password)
            
            if not new_account:
                logger.error("\nFailed to add the account to the database.")
                return

            logger.info("Reading session file and saving to the database...")
            with open(session_file_path, 'rb') as f:
                session_bytes: bytes = f.read()

            await db_manager.add_or_update_session(db, new_account.account_id, session_bytes)
            
            logger.info(f"\nSuccess! Account '{args.name}' was added. Restart the bot to activate.")

    except Exception as e:
        logger.error(f"\nAn unexpected error occurred: {e}", exc_info=True)
    finally:
        if temp_client and temp_client.is_connected():
            await temp_client.disconnect()
        if os.path.exists(session_file_path):
            os.remove(session_file_path)
            logger.info(f"Cleaned up temporary session file: {session_file_path}")

async def delete_account_logic(args: argparse.Namespace) -> None:
    """Handles the logic for deleting an account."""
    logger.info(f"--- Deleting account: {args.name} ---")
    async with get_db() as db:
        account: Optional[Account] = await db_manager.get_account(db, args.name)
        if not account:
            logger.error(f"Error: Account '{args.name}' not found.")
            return

        confirm = input(f"Are you sure you want to permanently delete account '{args.name}'? (yes/no): ").strip().lower()
        if confirm == 'yes':
            if await db_manager.delete_account(db, args.name):
                logger.info(f"Successfully deleted account '{args.name}'. Restart the bot for changes to take effect.")
            else:
                logger.error(f"Failed to delete account '{args.name}'.")
        else:
            logger.info("Deletion cancelled.")

async def toggle_account_logic(args: argparse.Namespace) -> None:
    """Handles the logic for enabling or disabling an account."""
    logger.info(f"--- Toggling account status: {args.name} ---")
    async with get_db() as db:
        new_status: Optional[bool] = await db_manager.toggle_account_status(db, args.name)
        if new_status is None:
            logger.error(f"Error: Account '{args.name}' not found.")
        else:
            status_text = "ENABLED" if new_status else "DISABLED"
            logger.info(f"Account '{args.name}' is now {status_text}. Restart the bot for changes to take effect.")

async def edit_account_logic(args: argparse.Namespace) -> None:
    """Handles the logic for editing an account's properties."""
    logger.info(f"--- Editing account: {args.name} ---")
    async with get_db() as db:
        account: Optional[Account] = await db_manager.get_account(db, args.name)
        if not account:
            logger.error(f"Error: Account '{args.name}' not found.")
            return

        updated_fields: List[str] = []
        if args.lang is not None:
            account.lang_code = args.lang
            updated_fields.append("language")
        if args.enable:
            account.is_enabled = True
            updated_fields.append("status (enabled)")
        if args.disable:
            account.is_enabled = False
            updated_fields.append("status (disabled)")
        if args.device_model is not None:
            account.device_model = args.device_model
            updated_fields.append("device model")
        if args.clear_proxy:
            account.proxy_type = None
            account.proxy_ip = None
            account.proxy_port = None
            account.proxy_username = None
            account.proxy_password = None
            updated_fields.append("proxy (cleared)")
        else:
            if args.proxy_type is not None:
                account.proxy_type = args.proxy_type
                updated_fields.append("proxy type")
            if args.proxy_ip is not None:
                account.proxy_ip = args.proxy_ip
                updated_fields.append("proxy IP")
            if args.proxy_port is not None:
                account.proxy_port = args.proxy_port
                updated_fields.append("proxy port")
            if args.proxy_user is not None:
                account.proxy_username = encryption_manager.encrypt(args.proxy_user.encode()) if args.proxy_user else None
                updated_fields.append("proxy username")
            if args.proxy_pass is not None:
                account.proxy_password = encryption_manager.encrypt(args.proxy_pass.encode()) if args.proxy_pass else None
                updated_fields.append("proxy password")

        if updated_fields:
            await db.commit()
            logger.info(f"Successfully updated fields for '{args.name}': {', '.join(updated_fields)}.")
            logger.info("Restart the bot for changes to take effect.")
        else:
            logger.info("No changes specified. Nothing to update.")

async def main() -> None:
    """The main entry point for the CLI script."""
    parser = argparse.ArgumentParser(description="DeBot Account Management CLI")
    subparsers = parser.add_subparsers(dest="command", required=True, help="Available commands")

    # Add command
    parser_add = subparsers.add_parser("add", help="Add a new account via interactive login")
    parser_add.add_argument("name", help="Unique name for the new account")
    parser_add.set_defaults(func=add_account_logic)

    # Delete command
    parser_delete = subparsers.add_parser("delete", help="Permanently delete an account")
    parser_delete.add_argument("name", help="Name of the account to delete")
    parser_delete.set_defaults(func=delete_account_logic)

    # Toggle command
    parser_toggle = subparsers.add_parser("toggle", help="Enable or disable an account")
    parser_toggle.add_argument("name", help="Name of the account to toggle")
    parser_toggle.set_defaults(func=toggle_account_logic)

    # Edit command
    parser_edit = subparsers.add_parser("edit", help="Edit properties of an existing account")
    parser_edit.add_argument("name", help="Name of the account to edit")
    parser_edit.add_argument("--lang", help="Set a new language code (e.g., en)")
    status_group = parser_edit.add_mutually_exclusive_group()
    status_group.add_argument("--enable", action="store_true", help="Enable the account")
    status_group.add_argument("--disable", action="store_true", help="Disable the account")
    parser_edit.add_argument("--device-model", help="Set a new device model string")
    proxy_group = parser_edit.add_argument_group("Proxy Options")
    proxy_group.add_argument("--proxy-type", choices=["http", "socks4", "socks5"], help="Set proxy type")
    proxy_group.add_argument("--proxy-ip", help="Set proxy IP address")
    proxy_group.add_argument("--proxy-port", type=int, help="Set proxy port")
    proxy_group.add_argument("--proxy-user", help="Set proxy username. Use '' for empty.")
    proxy_group.add_argument("--proxy-pass", help="Set proxy password. Use '' for empty.")
    proxy_group.add_argument("--clear-proxy", action="store_true", help="Remove all proxy settings for this account")
    parser_edit.set_defaults(func=edit_account_logic)

    args: argparse.Namespace = parser.parse_args()
    
    await initialize_database()
    await args.func(args)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, EOFError):
        logger.info("\nOperation cancelled by user.")
