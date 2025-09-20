import asyncio
import sys
from pathlib import Path
import getpass
import argparse

# Add project root to sys.path
project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from userbot.src.db.session import get_db, initialize_database
import userbot.src.db_manager as db_manager
from userbot.src.encrypt import encryption_manager
from userbot import FAKE

async def add_account_logic(args):
    """Logic to add a new account."""
    print(f"--- Adding new account: {args.name} ---")
    async with get_db() as db:
        if await db_manager.get_account(db, args.name):
            print(f"Error: Account '{args.name}' already exists.")
            return

        api_id = input("Enter API ID: ").strip()
        api_hash = getpass.getpass("Enter API Hash: ").strip()
        lang_code = input("Enter language code (e.g., ru, en) [ru]: ").strip() or 'ru'
        is_enabled = input("Enable this account now? (yes/no) [yes]: ").strip().lower() != 'no'
        
        device_model = FAKE.user_agent()
        system_version = f"SDK {FAKE.random_int(min=28, max=33)}"
        app_version = f"{FAKE.random_int(min=9, max=10)}.{FAKE.random_int(min=0, max=9)}.{FAKE.random_int(min=0, max=9)}"
        
        new_account = await db_manager.add_account(
            db, args.name, api_id, api_hash, lang_code, is_enabled,
            device_model, system_version, app_version
        )
        if new_account:
            print(f"\nSuccess! Account '{args.name}' was added.")
        else:
            print("\nFailed to add the account.")

async def toggle_account_logic(args):
    """Logic to toggle an account's status."""
    print(f"--- Toggling account: {args.name} ---")
    async with get_db() as db:
        new_status = await db_manager.toggle_account_status(db, args.name)
        if new_status is None:
            print(f"Error: Account '{args.name}' not found.")
        else:
            status_str = "ENABLED" if new_status else "DISABLED"
            print(f"Success! Account '{args.name}' is now {status_str}.")

async def delete_account_logic(args):
    """Logic to delete an account."""
    print(f"--- Deleting account: {args.name} ---")
    confirm = input(f"Are you sure you want to permanently delete '{args.name}'? (yes/no): ").lower()
    if confirm == 'yes':
        async with get_db() as db:
            if await db_manager.delete_account(db, args.name):
                print(f"Success! Account '{args.name}' has been deleted.")
            else:
                print(f"Error: Account '{args.name}' not found.")
    else:
        print("Deletion cancelled.")

async def edit_account_logic(args):
    """Logic to edit an account's properties."""
    print(f"--- Editing account: {args.name} ---")
    async with get_db() as db:
        account = await db_manager.get_account(db, args.name)
        if not account:
            print(f"Error: Account '{args.name}' not found.")
            return

        updated_fields = []
        if args.lang:
            account.lang_code = args.lang
            updated_fields.append(f"Language set to '{args.lang}'")
        if args.enable:
            account.is_enabled = True
            updated_fields.append("Account ENABLED")
        if args.disable:
            account.is_enabled = False
            updated_fields.append("Account DISABLED")
        if args.device_model:
            account.device_model = args.device_model
            updated_fields.append("Device model updated")
        
        if args.clear_proxy:
            account.proxy_type = None
            account.proxy_ip = None
            account.proxy_port = None
            account.proxy_username = None
            account.proxy_password = None
            updated_fields.append("Proxy settings CLEARED")
        elif args.proxy_type:
            account.proxy_type = args.proxy_type
            account.proxy_ip = args.proxy_ip
            account.proxy_port = args.proxy_port
            account.proxy_username = encryption_manager.encrypt(args.proxy_user.encode()) if args.proxy_user else None
            account.proxy_password = encryption_manager.encrypt(args.proxy_pass.encode()) if args.proxy_pass else None
            updated_fields.append("Proxy settings UPDATED")
        
        if updated_fields:
            print("Success! The following fields were updated:")
            for field in updated_fields:
                print(f"- {field}")
        else:
            print("No changes specified. Use --help for options.")

async def main():
    """Main function to parse arguments and dispatch commands."""
    parser = argparse.ArgumentParser(description="DeBot Account Management CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    parser_add = subparsers.add_parser("add", help="Add a new account")
    parser_add.add_argument("name", help="Unique name for the new account")
    parser_add.set_defaults(func=add_account_logic)
    
    parser_toggle = subparsers.add_parser("toggle", help="Enable or disable an account")
    parser_toggle.add_argument("name", help="Name of the account to toggle")
    parser_toggle.set_defaults(func=toggle_account_logic)

    parser_delete = subparsers.add_parser("delete", help="Delete an account permanently")
    parser_delete.add_argument("name", help="Name of the account to delete")
    parser_delete.set_defaults(func=delete_account_logic)

    parser_edit = subparsers.add_parser("edit", help="Edit account properties")
    parser_edit.add_argument("name", help="Name of the account to edit")
    parser_edit.add_argument("--lang", help="Set a new language code (e.g., en)")
    status_group = parser_edit.add_mutually_exclusive_group()
    status_group.add_argument("--enable", action="store_true", help="Enable the account")
    status_group.add_argument("--disable", action="store_true", help="Disable the account")
    parser_edit.add_argument("--device-model", help="Set a new device model string")
    
    proxy_group = parser_edit.add_argument_group("Proxy Options")
    proxy_group.add_argument("--proxy-type", choices=['http', 'socks4', 'socks5'], help="Set proxy type")
    proxy_group.add_argument("--proxy-ip", help="Set proxy IP address")
    proxy_group.add_argument("--proxy-port", type=int, help="Set proxy port")
    proxy_group.add_argument("--proxy-user", help="Set proxy username (optional)")
    proxy_group.add_argument("--proxy-pass", help="Set proxy password (optional)")
    proxy_group.add_argument("--clear-proxy", action="store_true", help="Clear all proxy settings for the account")
    parser_edit.set_defaults(func=edit_account_logic)

    args = parser.parse_args()
    
    await initialize_database()
    await args.func(args)

if __name__ == "__main__":
    asyncio.run(main())
