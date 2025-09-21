import asyncio
import io
import logging
import os
import shlex
import sys
import time
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple

from telethon import events
from telethon.tl.types import Message
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
        await event.edit(await event.client.get_string("help_logs_usage"), parse_mode="markdown")
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
        finally:
            await event.delete()
        return

    # --- Log Fetching Logic ---
    mode: str = "tail"
    limit: int = 100
    level: Optional[str] = None
    source: Optional[str] = None
    
    if args and args[0].lower() in ["head", "tail"]:
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
        parse_mode="markdown"
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
    await event.edit("\n".join(response_lines), parse_mode="markdown")

async def add_account_handler(event: events.NewMessage.Event):
    account_name: str = event.pattern_match.group(1)
    session_file_path: str = f"temp_add_{account_name}.session"
    temp_client: Optional[TelegramClient] = None
    
    try:
        async with event.client.conversation(event.chat_id, timeout=600) as conv:
            msg1 = await conv.send_message(await event.client.get_string("adding_account", account_name=account_name))
            api_id_resp: Message = await conv.get_response()
            api_id = api_id_resp.text.strip()
            await api_id_resp.delete()
            
            msg2 = await conv.send_message(await event.client.get_string("prompt_api_hash"))
            api_hash_resp: Message = await conv.get_response()
            api_hash = api_hash_resp.text.strip()
            await msg1.delete()
            await msg2.delete()
            await api_hash_resp.delete()
            
            status_msg = await conv.send_message(await event.client.get_string("verifying_creds"))
            temp_client = TelegramClient(SQLiteSession(session_file_path), int(api_id), api_hash)
            
            await temp_client.connect()
            if not await temp_client.is_user_authorized():
                await status_msg.delete()
                phone_msg = await conv.send_message("Требуется вход. Введите номер телефона:")
                phone_resp = await conv.get_response()
                phone = phone_resp.text.strip()
                await phone_msg.delete()
                await phone_resp.delete()

                await temp_client.send_code_request(phone)

                code_msg = await conv.send_message("Код отправлен. Введите его:")
                code_resp = await conv.get_response()
                code = code_resp.text.strip()
                await code_msg.delete()
                await code_resp.delete()
                try:
                    await temp_client.sign_in(phone=phone, code=code)
                except SessionPasswordNeededError:
                    pass_msg = await conv.send_message(await event.client.get_string("prompt_2fa"))
                    pass_resp = await conv.get_response()
                    two_fa_pass = pass_resp.text.strip()
                    await pass_msg.delete()
                    await pass_resp.delete()
                    await temp_client.sign_in(password=two_fa_pass)
            
            me = await temp_client.get_me(input_peer=True)
            user_id = me.user_id
            access_hash = me.access_hash
            await temp_client.disconnect()
            await status_msg.edit(await event.client.get_string("verifying_creds"))

            async with get_db() as db:
                existing = await db_manager.get_account_by_user_id(db, user_id)
                if existing:
                    await status_msg.edit(await event.client.get_string("err_duplicate_session", user_id=user_id, existing_name=existing.account_name))
                    return

            lang_msg = await conv.send_message(await event.client.get_string("prompt_lang"))
            lang_resp = await conv.get_response()
            lang_code = lang_resp.text.strip() or 'ru'
            await lang_msg.delete()
            await lang_resp.delete()

            act_msg = await conv.send_message(await event.client.get_string("prompt_activate"))
            act_resp = await conv.get_response()
            is_enabled = act_resp.text.lower().startswith(('y', 'д'))
            await act_msg.delete()
            await act_resp.delete()
            
            device_details = _generate_random_device()
            
            await status_msg.edit(await event.client.get_string("saving_to_db"))
            async with get_db() as db:
                new_acc = await db_manager.add_account(
                    db, account_name, api_id, api_hash, lang_code, is_enabled,
                    device_details['device_model'], device_details['system_version'], device_details['app_version'],
                    user_id, access_hash
                )
                if not new_acc:
                    await status_msg.edit(await event.client.get_string("add_acc_fail", account_name=account_name))
                    return
                
                with open(session_file_path, 'rb') as f:
                    session_bytes: bytes = f.read()
                await db_manager.add_or_update_session(db, new_acc.account_id, session_bytes)
            
            await status_msg.edit(await event.client.get_string("add_acc_success", account_name=account_name))

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
    """Handles the .help command, showing a list or extended help."""
    command_to_get: Optional[str] = event.pattern_match.group(1)
    client: TelegramClient = event.client
    account_id: Optional[int] = client.current_account_id
    
    # --- Extended Help Logic ---
    if command_to_get:
        cmd: str = f".{command_to_get.strip().lower()}"
        
        core_commands_ext: Dict[str, str] = {
            ".ping": "help_ext_ping", ".restart": "help_ext_restart", ".listaccs": "help_ext_listaccs",
            ".addacc": "help_ext_addacc", ".delacc": "help_ext_delacc", ".toggleacc": "help_ext_toggleacc",
            ".setlang": "help_ext_setlang", ".logs": "help_ext_logs", ".about": "help_ext_about",
            ".addmod": "help_ext_addmod", ".delmod": "help_ext_delmod", ".trustmod": "help_ext_trustmod",
            ".configmod": "help_ext_configmod", ".updatemodules": "help_ext_updatemodules",
        }
        
        for core_cmd, locale_key in core_commands_ext.items():
            if cmd.startswith(core_cmd):
                help_text: str = await client.get_string(locale_key)
                await event.edit(help_text, parse_mode="markdown")
                return

        if account_id and account_id in GLOBAL_HELP_INFO:
            for mod_info in GLOBAL_HELP_INFO[account_id].values():
                if mod_info.ext_descriptions:
                    for i, pattern in enumerate(mod_info.patterns):
                        if cmd.startswith(pattern.split(" ")[0]):
                            await event.edit(mod_info.ext_descriptions[i], parse_mode="markdown")
                            return
        
        await event.edit(await client.get_string("help_not_found", command=cmd))
        return

    # --- Main Help Menu Logic ---
    categories: Dict[str, List[str]] = {}
    
    core_commands: List[Tuple[str, str, str]] = [
        ("Управление", ".listaccs", "help_listaccs"), ("Управление", ".addacc <name>", "help_addacc"),
        ("Управление", ".delacc <name>", "help_delacc"), ("Управление", ".toggleacc <name>", "help_toggleacc"),
        ("Управление", ".setlang <code|url>", "help_setlang"),
        ("Модули", ".addmod", "help_addmod"), ("Модули", ".delmod <name>", "help_delmod"),
        ("Модули", ".trustmod <name>", "help_trustmod"),("Модули", ".configmod <...>", "help_configmod"),
        ("Утилиты", ".ping", "help_ping"), ("Утилиты", ".restart", "help_restart"),
        ("Утилиты", ".logs", "help_logs"),("Утилиты", ".updatemodules", "help_updatemodules"),
        ("Утилиты", ".about", "help_about"),
    ]
    for category, pattern, key in core_commands:
        if category not in categories:
            categories[category] = []
        desc: str = await client.get_string(key)
        categories[category].append(f"`{pattern}` - {desc}")

    if account_id and account_id in GLOBAL_HELP_INFO:
        for mod_name, mod_info in GLOBAL_HELP_INFO[account_id].items():
            cat_name: str = mod_info.category.capitalize()
            if cat_name not in categories:
                categories[cat_name] = []
            for i, pattern in enumerate(mod_info.patterns):
                desc: str = mod_info.descriptions[i]
                categories[cat_name].append(f"`{pattern}` - {desc}")
    
    final_text_parts: List[str] = [await client.get_string("help_header")]
    for i, (category, cmds) in enumerate(categories.items()):
        final_text_parts.append(f"\n╭ **{category}**")
        for j, cmd_text in enumerate(cmds):
            prefix = "└" if j == len(cmds) - 1 else "├"
            final_text_parts.append(f"{prefix} {cmd_text}")
    
    await event.edit("\n".join(final_text_parts), parse_mode="markdown")

async def about_command_handler(event: events.NewMessage.Event):
    await event.edit(await event.client.get_string("about_text"), parse_mode="markdown")

async def restart_handler(event: events.NewMessage.Event):
    await event.edit(await event.client.get_string("restarting_now"), pa
