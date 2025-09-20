import asyncio
import gc
import logging
import subprocess
import sys
from typing import Dict, Any, Optional, List, Set

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from rich.console import Console
from telethon import events, helpers
from telethon.errors import SessionPasswordNeededError
from telethon.sessions import StringSession

from userbot import ACTIVE_CLIENTS, LOOP, GLOBAL_HELP_INFO, FAKE, TelegramClient
from userbot.src.config import GC_INTERVAL_SECONDS
from userbot.src.db.session import get_db
import userbot.src.db_manager as db_manager
from userbot.src.module_parser import parse_module_metadata

console: Console = Console()
logger: logging.Logger = logging.getLogger(__name__)

# --- Helper Functions ---
async def get_account_id_from_client(client) -> int | None:
    return next((acc_id for acc_id, c in ACTIVE_CLIENTS.items() if c == client), None)

# --- Module Management ---
async def delmod_handler(event: events.NewMessage.Event):
    """Handles unlinking a module and safely uninstalling its dependencies."""
    # Simplified handler logic for brevity
    module_name_to_delete = event.pattern_match.group(1)
    account_id = await get_account_id_from_client(event.client)
    if not account_id: return

    uninstalled_deps: List[str] = []
    async with get_db() as db:
        module_to_delete = await db_manager.get_module(db, module_name_to_delete)
        if not module_to_delete:
            await event.edit(f"Модуль '{module_name_to_delete}' не найден.")
            return

        # 1. Get module dependencies
        dependencies_to_check: List[str] = []
        try:
            with open(module_to_delete.module_path, 'r', encoding='utf-8') as f:
                metadata, _ = parse_module_metadata(f.read())
                dependencies_to_check = metadata.get("requires", [])
        except FileNotFoundError:
            logger.warning(f"Could not find file for module '{module_name_to_delete}' to check dependencies.")

        # 2. Unlink module from account
        await db_manager.unlink_module_from_account(db, account_id, module_to_delete.module_id)

        # 3. Check if dependencies are used by other modules
        if dependencies_to_check:
            all_other_deps: Set[str] = set()
            all_active_modules = await db_manager.get_all_active_modules(db) # Needs implementation
            for mod in all_active_modules:
                if mod.module_id == module_to_delete.module_id: continue
                try:
                    with open(mod.module_path, 'r', encoding='utf-8') as f:
                        meta, _ = parse_module_metadata(f.read())
                        all_other_deps.update(meta.get("requires", []))
                except FileNotFoundError:
                    continue
            
            # 4. Uninstall unused dependencies
            for dep in dependencies_to_check:
                if dep not in all_other_deps:
                    try:
                        subprocess.run([sys.executable, "-m", "pip", "uninstall", "-y", dep], check=True)
                        uninstalled_deps.append(dep)
                        logger.info(f"Uninstalled unused dependency: {dep}")
                    except subprocess.CalledProcessError:
                        logger.error(f"Failed to uninstall dependency: {dep}")

    response = f"Модуль '{module_name_to_delete}' отвязан."
    if uninstalled_deps:
        response += f"\nУдалены зависимости: `{' '.join(uninstalled_deps)}`"
    
    await event.edit(response)


# --- Account Management Handlers ---
async def list_accounts_handler(event: events.NewMessage.Event):
    """Lists all accounts in the database with their status."""
    await event.edit(await event.client.get_string("verifying_creds"))
    header = await event.client.get_string("account_list_header")
    response_lines = [header]
    async with get_db() as db:
        all_accs = await db_manager.get_all_accounts(db)
        if not all_accs:
            response_lines.append(await event.client.get_string("account_list_none"))
        else:
            for acc in all_accs:
                status_icon = "🟢" if acc.is_enabled else "🔴"
                status_text = await event.client.get_string("status_enabled" if acc.is_enabled else "status_disabled")
                last_used = ""
                if not acc.is_enabled and acc.session and acc.session.last_used_at:
                    dt = acc.session.last_used_at.strftime('%Y-%m-%d %H:%M')
                    last_used = await event.client.get_string("last_active", datetime=dt)
                
                response_lines.append(
                    await event.client.get_string(
                        "account_list_entry",
                        status_icon=status_icon, account_name=acc.account_name,
                        account_id=acc.account_id, status_text=status_text, last_used=last_used
                    )
                )
    await event.edit("\n".join(response_lines), parse_mode="html")

async def add_account_handler(event: events.NewMessage.Event):
    """Interactively adds a new account session."""
    account_name = event.pattern_match.group(1)
    
    try:
        async with event.client.conversation(event.chat_id, timeout=600) as conv:
            await conv.send_message(await event.client.get_string("adding_account", account_name=account_name))
            api_id_resp = await conv.get_response(); api_id = api_id_resp.text.strip()
            await conv.send_message(await event.client.get_string("prompt_api_hash"))
            api_hash_resp = await conv.get_response(); api_hash = api_hash_resp.text.strip()
            
            await conv.send_message(await event.client.get_string("verifying_creds"))
            temp_client = TelegramClient(StringSession(), int(api_id), api_hash)
            user_id, two_fa_pass = None, None
            try:
                await temp_client.connect()
                if not await temp_client.is_user_authorized():
                    raise ValueError("Failed to authorize, manual sign-in flow is complex for this example.")
            except SessionPasswordNeededError:
                await conv.send_message(await event.client.get_string("prompt_2fa"))
                two_fa_pass_resp = await conv.get_response(); two_fa_pass = two_fa_pass_resp.text.strip()
                await temp_client.sign_in(password=two_fa_pass)
            
            me = await temp_client.get_me(); user_id = me.id
            await temp_client.disconnect()

            async with get_db() as db:
                existing = await db_manager.get_account_by_user_id(db, user_id)
                if existing:
                    await conv.send_message(await event.client.get_string("err_duplicate_session", user_id=user_id, existing_name=existing.account_name))
                    return

            await conv.send_message(await event.client.get_string("prompt_lang")); lang_code = (await conv.get_response()).text.strip() or 'ru'
            await conv.send_message(await event.client.get_string("prompt_activate")); is_enabled = (await conv.get_response()).text.lower().startswith('д')
            
            device_model, system_version, app_version = FAKE.android_platform_token(), "SDK 31", "10.1.0"
            
            await conv.send_message(await event.client.get_string("saving_to_db"))
            async with get_db() as db:
                new_acc = await db_manager.add_account(
                    db, account_name, api_id, api_hash, lang_code, is_enabled,
                    device_model, system_version, app_version, user_id
                )
            
            if new_acc:
                await conv.send_message(await event.client.get_string("add_acc_success", account_name=account_name))
            else:
                await conv.send_message(await event.client.get_string("add_acc_fail", account_name=account_name))

    except asyncio.TimeoutError:
        await event.respond(await event.client.get_string("add_acc_timeout"))
    except Exception as e:
        logger.error(f"Error in .addacc handler: {e}", exc_info=True)
        await event.respond(await event.client.get_string("generic_error", error=str(e)))

async def delete_account_handler(event: events.NewMessage.Event):
    """Deletes an account from the database."""
    account_name = event.pattern_match.group(1)
    async with event.client.conversation(event.chat_id, timeout=60) as conv:
        await conv.send_message(await event.client.get_string("confirm_delete", account_name=account_name))
        confirmation = await conv.get_response()
        if confirmation.text.lower() in ['да', 'yes']:
            async with get_db() as db:
                success = await db_manager.delete_account(db, account_name)
            if success:
                await conv.send_message(await event.client.get_string("delete_success", account_name=account_name))
            else:
                await conv.send_message(await event.client.get_string("delete_fail", account_name=account_name))
        else:
            await conv.send_message(await event.client.get_string("delete_cancelled"))

async def toggle_account_handler(event: events.NewMessage.Event):
    """Enables or disables an account."""
    account_name = event.pattern_match.group(1)
    async with get_db() as db:
        new_status = await db_manager.toggle_account_status(db, account_name)
    
    if new_status is None:
        await event.edit(await event.client.get_string("toggle_not_found", account_name=account_name))
    elif new_status is True:
        await event.edit(await event.client.get_string("toggle_enabled", account_name=account_name))
    else:
        await event.edit(await event.client.get_string("toggle_disabled", account_name=account_name))

async def set_lang_handler(event: events.NewMessage.Event):
    """Sets the language for the current account."""
    lang_code = event.pattern_match.group(1).lower()
    account_id = await get_account_id_from_client(event.client)
    if not account_id: return

    async with get_db() as db:
        success = await db_manager.update_account_lang(db, account_id, lang_code)
    
    if success:
        event.client.lang_code = lang_code
        await event.edit(await event.client.get_string("lang_updated", lang_code=lang_code))
    else:
        await event.edit(await event.client.get_string("lang_update_fail"))

async def help_commands_handler(event: events.NewMessage.Event):
    """Displays the help message."""
    help_management = "\n".join([
        f"<code>.listaccs</code> - {await event.client.get_string('help_listaccs')}",
        f"<code>.addacc &lt;name&gt;</code> - {await event.client.get_string('help_addacc')}",
        f"<code>.delacc &lt;name&gt;</code> - {await event.client.get_string('help_delacc')}",
        f"<code>.toggleacc &lt;name&gt;</code> - {await event.client.get_string('help_toggleacc')}",
        f"<code>.setlang &lt;code&gt;</code> - {await event.client.get_string('help_setlang')}",
        f"<code>.about</code> - {await event.client.get_string('help_about')}",
    ])
    
    final_text = f"{await event.client.get_string('help_header_management')}\n{help_management}"
    await event.edit(final_text, parse_mode="HTML")

async def about_command_handler(event: events.NewMessage.Event):
    """Displays information about the userbot."""
    await event.edit(await event.client.get_string("about_text"), parse_mode="HTML")

# --- Main Execution ---
if __name__ == "__main__":
    console.print(text2art("DeBot", font="random", chr_ignore=True), style="cyan")
    scheduler = AsyncIOScheduler(timezone="UTC")
    scheduler.add_job(gc.collect, 'interval', seconds=GC_INTERVAL_SECONDS, id='gc_job')
    scheduler.start()
    
    try:
        LOOP.run_forever()
    except KeyboardInterrupt:
        console.print("\n[MAIN] - Userbot stopped by user.", style="bold yellow")
    finally:
        if scheduler.running: scheduler.shutdown()
