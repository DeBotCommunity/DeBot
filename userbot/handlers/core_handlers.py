import asyncio
import io
import json
import logging
import os
import shlex
import shutil
import subprocess
import sys
import tempfile
import time
import importlib
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

from telethon import events
from telethon.tl.types import Message, DocumentAttributeFilename
from telethon.errors import SessionPasswordNeededError
from telethon.sessions import SQLiteSession
from telethon.tl.functions.updates import GetStateRequest

from userbot import TelegramClient, FAKE, GLOBAL_HELP_INFO, _generate_random_device
from userbot.db.session import get_db
from userbot.db import db_manager
from userbot.core.locales import translator
from userbot.utils.module_parser import parse_module_metadata
from userbot.utils.module_client import ModuleClient
from userbot.utils.encrypt import encryption_manager

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
async def load_account_modules(account_id: int, client: TelegramClient):
    """
    Dynamically loads all active modules for a given account.

    Args:
        account_id (int): The ID of the account for which to load modules.
        client (TelegramClient): The client instance for this account.
    """
    logger.info(f"Loading modules for account_id: {account_id}")
    async with get_db() as db:
        modules_to_load = await db_manager.get_active_modules_for_account(db, account_id)

    for link in modules_to_load:
        module_name: str = link.module.module_name
        try:
            # Modules are now in their own directories
            py_module = importlib.import_module(f"userbot.modules.{module_name}.{module_name}")
            importlib.reload(py_module)

            if not hasattr(py_module, "register") or not hasattr(py_module, "info"):
                logger.warning(f"Module '{module_name}' is malformed (missing register or info). Skipping.")
                continue

            GLOBAL_HELP_INFO[account_id][module_name] = py_module.info

            client_to_pass: TelegramClient | ModuleClient = client
            is_trusted_in_db: bool = link.is_trusted
            requires_trust: bool = getattr(py_module, "__trusted__", False)
            
            if requires_trust and not is_trusted_in_db:
                logger.warning(f"Module '{module_name}' requires trust but is not trusted for account {account_id}. Skipping handler registration.")
                continue
            elif not requires_trust:
                client_to_pass = ModuleClient(client)

            py_module.register(client_to_pass)
            logger.info(f"Successfully loaded module '{module_name}' for account {account_id}.")

        except ImportError as e:
            logger.error(f"Could not import module '{module_name}': {e}. Is the file present?")
        except Exception as e:
            logger.error(f"Failed to load module '{module_name}': {e}", exc_info=True)


async def addmod_handler(event: events.NewMessage.Event):
    """Handles adding a new module from a Git repository."""
    repo_url = event.pattern_match.group(1).strip()
    if not repo_url.startswith("http") or not repo_url.endswith(".git"):
        await event.edit(await event.client.get_string("addmod_err_invalid_url"))
        return

    await event.edit(await event.client.get_string("addmod_cloning"))
    
    with tempfile.TemporaryDirectory() as temp_dir:
        try:
            process = await asyncio.create_subprocess_exec(
                "git", "clone", "--depth=1", repo_url, temp_dir,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE
            )
            stdout, stderr = await process.communicate()
            if process.returncode != 0:
                await event.edit(await event.client.get_string("addmod_err_clone", error=stderr.decode()))
                return

            py_files = [p for p in Path(temp_dir).glob("*.py") if p.name != "__init__.py"]
            if len(py_files) != 1:
                await event.edit(await event.client.get_string("addmod_err_structure", count=len(py_files)))
                return

            module_file = py_files[0]
            module_name = module_file.stem
            
            with open(module_file, "r", encoding="utf-8") as f:
                source_code = f.read()
            
            metadata, error = parse_module_metadata(source_code)
            if error:
                await event.edit(await event.client.get_string("addmod_err_parse", error=error))
                return

            if metadata.get("requires"):
                await event.edit(await event.client.get_string("addmod_installing_deps", name=module_name))
                pip_process = await asyncio.create_subprocess_exec(
                    sys.executable, "-m", "pip", "install", *metadata["requires"],
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE
                )
                _, pip_stderr = await pip_process.communicate()
                if pip_process.returncode != 0:
                    await event.edit(await event.client.get_string("addmod_err_deps", error=pip_stderr.decode()))
                    return

            final_path_dir = Path("userbot/modules") / module_name
            if final_path_dir.exists():
                shutil.rmtree(final_path_dir)
            shutil.move(temp_dir, final_path_dir)
            
            final_path_file = final_path_dir / module_file.name

            account_id = await get_account_id_from_client(event.client)
            async with get_db() as db:
                module_info_dict = metadata.get("info", {})
                module_obj = await db_manager.get_or_create_module(
                    db, module_name, str(final_path_file), repo_url,
                    module_info_dict.get("descriptions", ["No description"])[0], 
                    module_info_dict.get("version")
                )
                
                initial_config = None
                if isinstance(metadata.get("config"), dict):
                    defaults = {k: v.get("default") for k, v in metadata["config"].items()}
                    config_bytes = json.dumps(defaults).encode('utf-8')
                    initial_config = encryption_manager.encrypt(config_bytes)

                await db_manager.link_module_to_account(db, account_id, module_obj.module_id, initial_config)

            final_msg = await event.client.get_string("addmod_success", name=module_name)
            if metadata.get("trusted"):
                final_msg += "\n" + await event.client.get_string("addmod_warn_trusted", name=module_name)
            
            await event.edit(final_msg)

        except Exception as e:
            logger.error(f"Error in addmod handler: {e}", exc_info=True)
            await event.edit(await event.client.get_string("generic_error", error=str(e)))


async def delmod_handler(event: events.NewMessage.Event):
    module_name = event.pattern_match.group(1).strip()
    account_id = await get_account_id_from_client(event.client)
    
    async with get_db() as db:
        module = await db_manager.get_module_by_name(db, module_name)
        if not module:
            await event.edit(await event.client.get_string("delmod_not_found", name=module_name))
            return
        
        success = await db_manager.unlink_module_from_account(db, account_id, module.module_id)
        if success:
            await event.edit(await event.client.get_string("delmod_success", name=module_name))
        else:
            await event.edit(await event.client.get_string("delmod_not_linked", name=module_name))


async def trustmod_handler(event: events.NewMessage.Event):
    module_name = event.pattern_match.group(1).strip()
    account_id = await get_account_id_from_client(event.client)

    async with get_db() as db:
        module = await db_manager.get_module_by_name(db, module_name)
        if not module:
            await event.edit(await event.client.get_string("delmod_not_found", name=module_name))
            return

        link = await db_manager.get_account_module_link(db, account_id, module.module_id)
        if not link:
            await event.edit(await event.client.get_string("delmod_not_linked", name=module_name))
            return

        success = await db_manager.set_module_trust(db, account_id, module.module_id, True)
        if success:
            await event.edit(await event.client.get_string("trustmod_success", name=module_name))
        else:
            await event.edit(await event.client.get_string("generic_error", error="Failed to update trust status."))


async def configmod_handler(event: events.NewMessage.Event):
    try:
        parts = shlex.split(event.pattern_match.group(1))
        if len(parts) != 3:
            raise ValueError
        module_name, key, value = parts
    except ValueError:
        await event.edit(await event.client.get_string("configmod_err_usage"))
        return
        
    account_id = await get_account_id_from_client(event.client)
    async with get_db() as db:
        module = await db_manager.get_module_by_name(db, module_name)
        if not module:
            await event.edit(await event.client.get_string("delmod_not_found", name=module_name))
            return

        current_config = await db_manager.get_module_config(db, account_id, module.module_id)
        if current_config is None:
            await event.edit(await event.client.get_string("configmod_no_config", name=module_name))
            return

        try:
            py_module = importlib.import_module(f"userbot.modules.{module_name}.{module_name}")
            default_val = py_module.__config__[key]["default"]
            if isinstance(default_val, bool):
                new_value = value.lower() in ("true", "1", "t", "yes")
            elif isinstance(default_val, int):
                new_value = int(value)
            elif isinstance(default_val, float):
                new_value = float(value)
            else:
                new_value = value
        except (ImportError, KeyError):
            await event.edit(await event.client.get_string("configmod_invalid_key", key=key))
            return
        except ValueError:
            await event.edit(await event.client.get_string("configmod_invalid_value", value=value, type=type(default_val).__name__))
            return

        current_config[key] = new_value
        success = await db_manager.set_module_config(db, account_id, module.module_id, current_config)
        
        if success:
            await event.edit(await event.client.get_string("configmod_success", key=key, name=module_name, value=new_value))
        else:
            await event.edit(await event.client.get_string("generic_error", error="Failed to save new configuration."))
    
async def update_module_handler(event: events.NewMessage.Event):
    module_name = event.pattern_match.group(1).strip()
    await event.edit(await event.client.get_string("updatemodule_starting", name=module_name))

    async with get_db() as db:
        module = await db_manager.get_module_by_name(db, module_name)
        if not module or not module.git_repo_url:
            await event.edit(await event.client.get_string("updatemodule_not_git", name=module_name))
            return
    
    module_dir = Path(module.module_path).parent

    try:
        process = await asyncio.create_subprocess_exec(
            "git", "-C", str(module_dir), "pull",
            stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
        stdout, stderr = await process.communicate()

        if process.returncode == 0:
            if "Already up to date" in stdout.decode():
                await event.edit(await event.client.get_string("updatemodule_no_changes", name=module_name))
            else:
                await event.edit(await event.client.get_string("updatemodule_success", name=module_name))
        else:
            await event.edit(await event.client.get_string("updatemodule_pull_failed_retrying", name=module_name))
            shutil.rmtree(module_dir)
            
            clone_process = await asyncio.create_subprocess_exec(
                "git", "clone", "--depth=1", module.git_repo_url, str(module_dir),
                stdout=subprocess.PIPE, stderr=subprocess.PIPE
            )
            _, clone_stderr = await clone_process.communicate()

            if clone_process.returncode == 0:
                await event.edit(await event.client.get_string("updatemodule_success", name=module_name))
            else:
                await event.edit(await event.client.get_string("updatemodule_clone_failed", name=module_name, error=clone_stderr.decode()))

    except Exception as e:
        await event.edit(await event.client.get_string("generic_error", error=str(e)))


async def update_modules_handler(event: events.NewMessage.Event):
    await event.edit(await event.client.get_string("updatemodules_starting"))
    
    async with get_db() as db:
        modules = await db_manager.get_all_updatable_modules(db)

    if not modules:
        await event.edit(await event.client.get_string("updatemodules_none_found"))
        return
    
    report = []
    for module in modules:
        module_dir = Path(module.module_path).parent
        try:
            process = await asyncio.create_subprocess_exec(
                "git", "-C", str(module_dir), "pull",
                stdout=subprocess.PIPE, stderr=subprocess.PIPE
            )
            stdout, _ = await process.communicate()
            output = stdout.decode()
            if "Already up to date" in output:
                report.append(f"✅ `{module.module_name}`: " + await event.client.get_string("updatemodule_status_latest"))
            else:
                report.append(f"🔄 `{module.module_name}`: " + await event.client.get_string("updatemodule_status_updated"))
        except Exception:
            report.append(f"❌ `{module.module_name}`: " + await event.client.get_string("updatemodule_status_failed"))

    await event.edit(
        await event.client.get_string("updatemodules_finished") + "\n\n" + "\n".join(report),
        parse_mode="markdown"
    )

async def logs_handler(event: events.NewMessage.Event):
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
        mode=mode, lines=limit, level=level or "ANY",
        source=source or "ANY", found=len(logs_list)
    )

    await event.delete()
    await event.client.send_file(
        event.chat_id, file=log_file, caption=caption,
        attributes=[DocumentAttributeFilename(filename)], parse_mode="markdown"
    )

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
                        "account_list_entry", status_icon=status_icon, account_name=acc.account_name,
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
    command_to_get: Optional[str] = event.pattern_match.group(1)
    client: TelegramClient = event.client
    account_id: Optional[int] = client.current_account_id
    if command_to_get:
        cmd: str = f".{command_to_get.strip().lower()}"
        core_commands_ext: Dict[str, str] = {
            ".ping": "help_ext_ping", ".restart": "help_ext_restart", ".listaccs": "help_ext_listaccs",
            ".addacc": "help_ext_addacc", ".delacc": "help_ext_delacc", ".toggleacc": "help_ext_toggleacc",
            ".setlang": "help_ext_setlang", ".logs": "help_ext_logs", ".about": "help_ext_about",
            ".addmod": "help_ext_addmod", ".delmod": "help_ext_delmod", ".trustmod": "help_ext_trustmod",
            ".configmod": "help_ext_configmod", ".updatemodule": "help_ext_updatemodule", ".updatemodules": "help_ext_updatemodules",
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

    categories: Dict[str, List[str]] = {}
    core_commands: List[Tuple[str, str, str]] = [
        ("help_category_management", ".listaccs", "help_listaccs"),
        ("help_category_management", ".addacc <name>", "help_addacc"),
        ("help_category_management", ".delacc <name>", "help_delacc"),
        ("help_category_management", ".toggleacc <name>", "help_toggleacc"),
        ("help_category_management", ".setlang <code|url>", "help_setlang"),
        ("help_category_modules", ".addmod <url>", "help_addmod"),
        ("help_category_modules", ".delmod <name>", "help_delmod"),
        ("help_category_modules", ".trustmod <name>", "help_trustmod"),
        ("help_category_modules", ".configmod <...>", "help_configmod"),
        ("help_category_modules", ".updatemodule <name>", "help_updatemodule"),
        ("help_category_modules", ".updatemodules", "help_updatemodules"),
        ("help_category_utilities", ".ping", "help_ping"),
        ("help_category_utilities", ".restart", "help_restart"),
        ("help_category_utilities", ".logs", "help_logs"),
        ("help_category_utilities", ".about", "help_about"),
    ]
    for category_key, pattern, desc_key in core_commands:
        translated_category: str = await client.get_string(category_key)
        if translated_category not in categories:
            categories[translated_category] = []
        desc: str = await client.get_string(desc_key)
        categories[translated_category].append(f"`{pattern}` - {desc}")
        
    if account_id and account_id in GLOBAL_HELP_INFO:
        for mod_name, mod_info in GLOBAL_HELP_INFO[account_id].items():
            category_key: str = f"help_category_{mod_info.category.lower()}"
            translated_cat_name: str = await client.get_string(category_key)
            if translated_cat_name == category_key:
                translated_cat_name = mod_info.category.capitalize()

            if translated_cat_name not in categories:
                categories[translated_cat_name] = []
                
            for i, pattern in enumerate(mod_info.patterns):
                desc: str = mod_info.descriptions[i]
                categories[translated_cat_name].append(f"`{pattern}` - {desc}")
                
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
    await event.edit(await event.client.get_string("restarting_now"), parse_mode="markdown")
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
    await event.edit(response_text, parse_mode="markdown")
