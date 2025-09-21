import asyncio
import io
import logging
import os
import shlex
import subprocess
import sys
from datetime import datetime
from typing import Dict, Any, List, Set, Optional

from telethon import events
from telethon.errors import SessionPasswordNeededError
from telethon.sessions import SQLiteSession

from userbot import TelegramClient, FAKE, GLOBAL_HELP_INFO, _generate_random_device, ACTIVE_CLIENTS
from userbot.src.db.session import get_db
import userbot.src.db_manager as db_manager
from userbot.src.module_parser import parse_module_metadata

logger: logging.Logger = logging.getLogger(__name__)

# --- Helper ---
async def get_account_id_from_client(client) -> int | None:
    # Access the override property directly
    return client.current_account_id if hasattr(client, 'current_account_id') else None

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
    await event.edit("Команда `.update_modules` в разработке.")

async def logs_handler(event: events.NewMessage.Event):
    await event.edit("Команда `.logs` в разработке.")

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
            await temp_client.disconnect() # Disconnect to save session file properly

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
                    account_name=account_name,
                    api_id=api_id,
                    api_hash=api_hash,
                    lang_code=lang_code,
                    is_enabled=is_enabled,
                    device_model=device_details['device_model'],
                    system_version=device_details['system_version'],
                    app_version=device_details['app_version'],
                    user_telegram_id=user_id,
                    access_hash=access_hash
                )
                if not new_acc:
                    await conv.send_message(await event.client.get_string("add_acc_fail", account_name=account_name))
                    return
                
                # Now extract session data and save it
                with open(session_file_path, 'rb') as f:
                    session_bytes: bytes = f.read()

                await db_manager.add_or_update_session(
                    db,
                    account_id=new_acc.account_id,
                    session_file=session_bytes
                )
            
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
    await event.edit(await event.client.get_string("about_text"), parse_mode="HTML")
