import asyncio
import io
import logging
import os
import shlex
import sys
import time
from datetime import datetime
from typing import Dict, Any, List, Optional

from telethon import events
from telethon.errors import SessionPasswordNeededError
from telethon.sessions import SQLiteSession
from telethon.tl.functions.updates import GetStateRequest
from telethon.tl.types import DocumentAttributeFilename

from userbot import TelegramClient, FAKE, GLOBAL_HELP_INFO, _generate_random_device
from userbot.src.db.session import get_db
import userbot.src.db_manager as db_manager
from userbot.src.locales import translator

logger: logging.Logger = logging.getLogger(__name__)

# --- Helper ---
async def get_account_id_from_client(client: TelegramClient) -> Optional[int]:
    """
    Safely retrieves the account_id associated with a client instance.

    Args:
        client (TelegramClient): The client instance.

    Returns:
        Optional[int]: The account ID if available, otherwise None.
    """
    return client.current_account_id

# --- Module Management ---
async def load_account_modules(account_id: int, client_instance: TelegramClient, current_help_info: Dict[str, str]):
    # Placeholder
    pass

async def addmod_handler(event: events.NewMessage.Event):
    await event.edit("Команда `.addmod` в разработке.")

async def delmod_handler(event: events.NewMessage.Event):
    await event.edit("Команда `.delmod` в разработке.")

async def trustmod_handler(event: events.NewMessage.Event):
    await event.edit("Команда `.trustmod` в разработке.")

async def configmod_handler(event: events.NewMessage.Event):
    await event.edit("Команда `.configmod` в разработке.")
    
async def update_modules_handler(event: events.NewMessage.Event):
    await event.edit("Команда `.updatemodules` в разработке.")

async def logs_handler(event: events.NewMessage.Event):
    """Handles the .logs command for fetching and managing logs."""
    await event.edit(await event.client.get_string("logs_processing"))
    
    try:
        args: List[str] = shlex.split(event.raw_text)[1:]
    except ValueError:
        await event.edit(await event.client.get_string("logs_err_args"))
        return

    if not args:
        await event.edit(await event.client.get_string("help_logs_usage"))
        return

    command: str = args[0].lower()

    if command == "purge":
        try:
            async with event.client.conversation(event.chat_id, timeout=60) as conv:
                await conv.send_message(await event.client.get_string("logs_confirm_purge"))
                response = await conv.get_response()
                if response.text.lower() in ("yes", "да"):
                    async with get_db() as db:
                        deleted_count = await db_manager.purge_logs(db)
                    await conv.send_message(await event.client.get_string("logs_purge_success", count=deleted_count))
                else:
                    await conv.send_message(await event.client.get_string("logs_purge_cancelled"))
        except asyncio.TimeoutError:
            await event.respond(await event.client.get_string("delete_timeout"))
        return

    # --- Log Fetching Logic ---
    mode: str = "tail"
    limit: int = 100
    level: Optional[str] = None
    source: Optional[str] = None
    
    # Parse arguments
    if args[0].lower() in ["head", "tail"]:
        mode = args.pop(0).lower()
    
    if args and args[0].isdigit():
        limit = int(args.pop(0))

    for arg in args:
        if "=" in arg:
            key, value = arg.split("=", 1)
            if key.lower() == "level":
                level = value.upper()
            elif key.lower() == "source":
                source = value

    async with get_db() as db:
        logs_list = await db_manager.get_logs_advanced(db, mode, limit, level, source)

    if not logs_list:
        await event.edit(await event.client.get_string("logs_not_found"))
        return

    # Prepare file and caption
    log_content: str = "\n".join(
        f"[{log.timestamp.strftime('%Y-%m-%d %H:%M:%S')}] [{log.level}] [{log.module_name or 'System'}] {log.message}"
        for log in logs_list
    )
    
    log_file = io.BytesIO(log_content.encode('utf-8'))
    filename = f"debot_logs_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
    
    caption: str = await event.client.get_string(
        "logs_caption",
        mode=mode,
        lines=limit,
        level=level or "ANY",
        source=source or "ANY",
        found=len(logs_list)
    )

    await event.delete()
    await event.client.send_file(
        event.chat_id,
        file=log_file,
        caption=caption,
        attributes=[DocumentAttributeFilename(filename)],
        parse_mode="HTML"
    )

# --- Account Management Handlers ---
async def list_accounts_handler(event: events.NewMessage.Event):
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
    account_name: str = event.pattern_match.group(1)
    session_file_path: str = f"temp_add_{account_name}.session"
    temp_client: Optional[TelegramClient] = None
    
    try:
        async with event.client.conversation(event.chat_id, timeout=600) as conv:
            await conv.send_message(await event.client.get_string("adding_account", account_name=account_name))
            api_id_resp = await conv.get_response(); api_id = api_id_resp.text.strip()
            await conv.send_message(await event.client.get_string("prompt_api_hash"))
            api_hash_resp = await conv.get_response(); api_hash = api_hash_resp.text.strip()
            
            await conv.send_message(await event.client.get_string("verifying_creds"))
            temp_client = TelegramClient(SQLiteSession(session_file_path), int(api_id), api_hash)
            
            await temp_client.connect()
            if not await temp_client.is_user_authorized():
                phone_resp = await conv.send_message("Требуется вход. Введите номер телефона:")
                phone = (await conv.get_response()).text.strip()
                await phone_resp.delete()
                await temp_client.send_code_request(phone)
                code_resp = await conv.send_message("Код отправлен. Введите его:")
                code = (await conv.get_response()).text.strip()
                await code_resp.delete()
                try:
                    await temp_client.sign_in(phone=phone, code=code)
                except SessionPasswordNeededError:
                    pass_resp = await conv.send_message(await event.client.get_string("prompt_2fa"))
                    two_fa_pass = (await conv.get_response()).text.strip()
                    await pass_resp.delete()
                    await temp_client.sign_in(password=two_fa_pass)
            
            me = await temp_client.get_me(input_peer=True)
            user_id = me.user_id
            access_hash = me.access_hash
            await temp_client.disconnect()

            async with get_db() as db:
                existing = await db_manager.get_account_by_user_id(db, user_id)
                if existing:
                    await conv.send_message(await event.client.get_string("err_duplicate_session", user_id=user_id, existing_name=existing.account_name))
                    return

            await conv.send_message(await event.client.get_string("prompt_lang")); lang_code = (await conv.get_response()).text.strip() or 'ru'
            await conv.send_message(await event.client.get_string("prompt_activate")); is_enabled = (await conv.get_response()).text.lower().startswith(('y', 'д'))
            
            device_details = _generate_random_device()
            
            await conv.send_message(await event.client.get_string("saving_to_db"))
            async with get_db() as db:
                new_acc = await db_manager.add_account(
                    db,
                    account_name=account_name, api_id=api_id, api_hash=api_hash, lang_code=lang_code, is_enabled=is_enabled,
                    device_model=device_details['device_model'], system_version=device_details['system_version'], app_version=device_details['app_version'],
                    user_telegram_id=user_id, access_hash=access_hash
                )
                if not new_acc:
                    await conv.send_message(await event.client.get_string("add_acc_fail", account_name=account_name))
                    return
                
                with open(session_file_path, 'rb') as f:
                    session_bytes: bytes = f.read()

                await db_manager.add_or_update_session(db, new_acc.account_id, session_bytes)
            
            await conv.send_message(await event.client.get_string("add_acc_success", account_name=account_name))

    except asyncio.TimeoutError:
        await event.respond(await event.client.get_string("add_acc_timeout"))
    except Exception as e:
        logger.error(f"Error in .addacc handler: {e}", exc_info=True)
        await event.respond(await event.client.get_string("generic_error", error=str(e)))
    finally:
        if temp_client and temp_client.is_connected():
            await temp_client.disconnect()
        if os.path.exists(session_file_path):
            os.remove(session_file_path)

async def delete_account_handler(event: events.NewMessage.Event):
    account_name = event.pattern_match.group(1)
    try:
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
    except asyncio.TimeoutError:
        await event.respond(await event.client.get_string("delete_timeout"))

async def toggle_account_handler(event: events.NewMessage.Event):
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
    identifier: str = event.pattern_match.group(1)
    account_id = await get_account_id_from_client(event.client)
    if not account_id: return

    await event.edit(await event.client.get_string("lang_downloading"))
    
    new_lang_code, error = await translator.load_language_pack(identifier)
    
    if error or not new_lang_code:
        await event.edit(await event.client.get_string("lang_download_fail", error=error))
        return

    async with get_db() as db:
        success = await db_manager.update_account_lang(db, account_id, new_lang_code)
    
    if success:
        event.client.lang_code = new_lang_code
        await event.edit(await event.client.get_string("lang_updated", lang_code=new_lang_code))
    else:
        await event.edit(await event.client.get_string("lang_update_fail"))

async def help_commands_handler(event: events.NewMessage.Event):
    # Part 1: Management
    help_management = "\n".join([
        f"<code>.listaccs</code> - {await event.client.get_string('help_listaccs')}",
        f"<code>.addacc &lt;name&gt;</code> - {await event.client.get_string('help_addacc')}",
        f"<code>.delacc &lt;name&gt;</code> - {await event.client.get_string('help_delacc')}",
        f"<code>.toggleacc &lt;name&gt;</code> - {await event.client.get_string('help_toggleacc')}",
        f"<code>.setlang &lt;code|url&gt;</code> - {await event.client.get_string('help_setlang')}"
    ])
    
    # Part 2: Module Management
    help_modules = "\n".join([
        f"<code>.addmod</code> - {await event.client.get_string('help_addmod')}",
        f"<code>.delmod &lt;name&gt;</code> - {await event.client.get_string('help_delmod')}",
        f"<code>.trustmod &lt;name&gt;</code> - {await event.client.get_string('help_trustmod')}",
        f"<code>.configmod &lt;...&gt;</code> - {await event.client.get_string('help_configmod')}"
    ])

    # Part 3: Utilities
    help_utils = "\n".join([
        f"<code>.ping</code> - {await event.client.get_string('help_ping')}",
        f"<code>.restart</code> - {await event.client.get_string('help_restart')}",
        f"<code>.logs</code> - {await event.client.get_string('help_logs')}",
        f"<code>.logs purge</code> - {await event.client.get_string('help_logs_purge')}",
        f"<code>.updatemodules</code> - {await event.client.get_string('help_updatemodules')}",
        f"<code>.about</code> - {await event.client.get_string('help_about')}"
    ])

    # Combine all parts
    final_text = (
        f"{await event.client.get_string('help_header_management')}\n{help_management}\n\n"
        f"{await event.client.get_string('help_header_modules')}\n{help_modules}\n\n"
        f"{await event.client.get_string('help_header_utils')}\n{help_utils}"
    )

    await event.edit(final_text, parse_mode="HTML")

async def about_command_handler(event: events.NewMessage.Event):
    await event.edit(await event.client.get_string("about_text"), parse_mode="HTML")

async def restart_handler(event: events.NewMessage.Event):
    await event.edit(await event.client.get_string("restarting_now"))
    await asyncio.sleep(1)
    sys.exit(0)

async def ping_handler(event: events.NewMessage.Event):
    start_time: float = time.time()
    await event.edit("Pinging...")
    
    api_start_time: float = time.time()
    await event.client(GetStateRequest())
    api_end_time: float = time.time()
    
    end_time: float = time.time()
    
    total_latency: float = (end_time - start_time) * 1000
    api_latency: float = (api_end_time - api_start_time) * 1000
    user_server_latency: float = total_latency - api_latency
    
    response_text = await event.client.get_string(
        "ping_response",
        user_server=f"{user_server_latency:.2f}",
        server_api=f"{api_latency:.2f}",
        total=f"{total_latency:.2f}"
    )
    await event.edit(response_text, parse_mode="HTML")
