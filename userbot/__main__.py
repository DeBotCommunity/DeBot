import importlib
import importlib.util
import os
import sys
import time
from pathlib import Path
import gc
from apscheduler.schedulers.asyncio import AsyncIOScheduler

import telethon
from art import text2art
from rich.console import Console # Console object is initialized in __main__
from telethon import events
import asyncio # Added for ensure_future in main

# Specific imports from userbot package & modules
# CLIENT and CURRENT_ACCOUNT_ID are removed for multi-account setup
# help_info is replaced by GLOBAL_HELP_INFO
from userbot import ACTIVE_CLIENTS, LOOP, GLOBAL_HELP_INFO, ALPHABET, MODULE_FOLDER 
from userbot.src.module_info import ModuleInfo # Import the new class
from userbot.src.db_manager import (
    get_active_modules_for_account,
    add_module as db_add_module,
    get_module as db_get_module,
    link_module_to_account,
    unlink_module_from_account,
    get_account_module, # To check if already linked
    update_account_proxy_settings # For .setproxy command
)
from userbot.src.encrypt import encryption_manager # For .setproxy command

# Global console object, will be initialized in __main__
console: Console = None

# Helper function to get account_id from client instance
async def get_account_id_from_client(event_or_client, active_clients_dict):
    client_instance = None
    if hasattr(event_or_client, 'client'): # It's an event object
        client_instance = event_or_client.client
    elif hasattr(event_or_client, 'list_event_handlers'): # It's likely a client object itself
        client_instance = event_or_client
    else:
        if console: console.print(f"[ERROR] get_account_id_from_client: Passed object is not an event or client.", style="bold red")
        return None

    for acc_id, client_obj in active_clients_dict.items():
        if client_obj == client_instance:
            return acc_id
    if console: console.print(f"[ERROR] get_account_id_from_client: Client not found in active_clients_dict.", style="bold red")
    return None

async def perform_garbage_collection():
    gc.collect()
    if console: # Ensure console is available
        console.print("-> [system] - Performed scheduled garbage collection.", style="dim blue")
    else:
        print("-> [system] - Performed scheduled garbage collection (console not available).")

def convert_to_fancy_font(text):
    converted_text = [ALPHABET.get(char, char) for char in text.lower()]
    return "".join(converted_text)

LOADED_MODULES_CACHE = {} # Key: (account_id, module_name), Value: module_obj

async def load_account_modules(account_id, client_instance, current_help_info): # Signature changed
    global console 
    if account_id is None: 
        if console: console.print(f"[MODULES] - CRITICAL: account_id is None for client {client_instance}. Cannot load modules.", style="bold red")
        else: print(f"[MODULES] - CRITICAL: account_id is None for client {client_instance}. Cannot load modules.")
        return
    if not console:
        print(f"[MODULES] - Console not initialized for load_account_modules (account: {account_id}).")
        return

    console.print(f"[MODULES] - Loading modules for account_id: {account_id}", style="yellow")
    try:
        active_modules = await get_active_modules_for_account(account_id) # Use passed account_id
    except Exception as e:
        console.print(f"[MODULES] - Error fetching active modules from DB for account {account_id}: {e}", style="bold red")
        return

    if not active_modules:
        console.print(f"[MODULES] - No active modules found for account {account_id}.", style="yellow")
        return

    loaded_count = 0
    for module_record in active_modules:
        module_name = module_record.get('module_name')
        module_path = module_record.get('module_path') 

        if not module_name or not module_path:
            console.print(f"[MODULES] - Skipping module with missing name or path: {module_record}", style="bold red")
            continue

        if not os.path.exists(module_path):
            console.print(f"[MODULES] - Module file not found: {module_path} for module {module_name}. Skipping.", style="bold red")
            continue
        
        import_name = module_path.replace(os.sep, ".").replace(".py", "")
        
        try:
            # Check if module is already loaded for THIS account
            if (account_id, module_name) in LOADED_MODULES_CACHE:
                module_obj = LOADED_MODULES_CACHE[(account_id, module_name)]
                console.print(f"[MODULES] - Module {module_name} (as {import_name}) already processed for account {account_id}. Using existing.", style="yellow")
                # Potentially re-apply handlers if module has specific registration logic
                if hasattr(module_obj, "register_handlers_on_client") and callable(module_obj.register_handlers_on_client):
                     module_obj.register_handlers_on_client(client_instance)
                     console.print(f"[MODULES] - Re-called register_handlers_on_client for {module_name} on account {account_id}", style="green")
            elif import_name in sys.modules:
                # Module file is in sys.modules (loaded by another account or globally)
                # We need to ensure its handlers are registered for *this* client_instance
                # and cache it for this account.
                module_obj = sys.modules[import_name]
                console.print(f"[MODULES] - Module {module_name} (as {import_name}) already in sys.modules. Applying to account {account_id}.", style="yellow")
                if hasattr(module_obj, "register_handlers_on_client") and callable(module_obj.register_handlers_on_client):
                    module_obj.register_handlers_on_client(client_instance)
                    console.print(f"[MODULES] - Called register_handlers_on_client for {module_name} on account {account_id}", style="green")
                # Even if no specific registration function, Telethon handlers defined at module level
                # might need re-evaluation or the module might need to be "activated" for this client.
                # This can be complex. For now, we assume simple modules or that Telethon handles it.
            else:
                spec = importlib.util.spec_from_file_location(import_name, module_path)
                if spec is None:
                    console.print(f"[MODULES] - Failed to create spec for {module_name} from {module_path} for account {account_id}", style="bold red")
                    continue
                module_obj = importlib.util.module_from_spec(spec)
                # Important: Add to sys.modules *before* exec_module to handle circular imports within the module
                sys.modules[import_name] = module_obj 
                spec.loader.exec_module(module_obj)
            
            LOADED_MODULES_CACHE[(account_id, module_name)] = module_obj # Cache per account
            console.print(f"[MODULES] - Successfully processed module: {module_name} (as {import_name}) for account {account_id}", style="bold green")
            loaded_count += 1

            if hasattr(module_obj, "info") and isinstance(module_obj.info, ModuleInfo):
                module_info_instance = module_obj.info
                category = module_info_instance.category
                if category:
                    if category not in current_help_info:
                        current_help_info[category] = f"<b>➖ {category.capitalize()}</b>"
                    
                    # patterns and descriptions are now lists in ModuleInfo
                    for i in range(len(module_info_instance.patterns)):
                        pattern_text = module_info_instance.patterns[i].strip()
                        if not pattern_text: continue
                        # Ensure descriptions list is long enough
                        desc_text = module_info_instance.descriptions[i].strip() if i < len(module_info_instance.descriptions) else "No description"
                        current_help_info[category] += f"\n<code>{pattern_text}</code> -> <i>{convert_to_fancy_font(desc_text)}</i>"
                else:
                    console.print(f"[MODULES] - Module {module_info_instance.name} has 'info' but no 'category'. Not added to help.", style="yellow")
            else:
                console.print(f"[MODULES] - Module {module_name} has no 'info' attribute of type ModuleInfo. Not added to help.", style="yellow")
        except Exception as e:
            console.print(f"[MODULES] - Error loading module {module_name} from {module_path}: {e}", style="bold red")
            if import_name in sys.modules:
                del sys.modules[import_name]
    
    console.print(f"[MODULES] - Total modules processed for account {account_id}: {loaded_count}/{len(active_modules)}", style="bold green")

# load_module_sortner function is removed.

async def addmod_handler(event): 
    # help_info (now GLOBAL_HELP_INFO) is accessed via current_account_id if needed directly here,
    # but module loading part uses the dict passed by start_individual_client.
    global console, GLOBAL_HELP_INFO, LOADED_MODULES_CACHE 
    
    current_account_id = await get_account_id_from_client(event, ACTIVE_CLIENTS)
    if current_account_id is None:
        await event.edit("Internal error: Could not identify account for this client.")
        return

    if not event.is_reply:
        await event.edit("❌ Ответьте на файл модуля (.py).")
        return

    reply_message = await event.get_reply_message()
    if not (reply_message.media and reply_message.media.document):
        await event.edit("❌ Ответьте на файл модуля (.py).")
        return

    document = reply_message.media.document
    if not (document.mime_type == "text/x-python" or document.mime_type == "application/x-python-code" or (document.attributes[0].file_name if document.attributes else "").endswith(".py")):
        await event.edit("❌ Это не похоже на Python файл (.py).")
        return

    file_name = "unknown_module.py"
    for attr in document.attributes:
        if hasattr(attr, 'file_name'):
            file_name = attr.file_name
            break
    
    if not file_name.endswith(".py"):
        await event.edit("❌ Имя файла должно оканчиваться на .py")
        return

    module_name_from_file = file_name[:-3] # Remove .py

    # Define module directory relative to this script's location
    # (userbot/__main__.py -> userbot/ is script_dir.parent)
    script_dir = Path(__file__).resolve().parent 
    # MODULE_FOLDER from config is "userbot.modules". We want a physical dir "userbot/modules".
    # So, if script_dir is <project_root>/userbot, modules_dir is <project_root>/userbot/modules
    modules_dir = script_dir / "modules"

    # Ensure the directory exists
    modules_dir.mkdir(parents=True, exist_ok=True)

    # download_path is now robustly defined
    download_path = modules_dir / file_name

    # For storing in DB, use a path relative to the project root (e.g., "userbot/modules/file.py")
    # Assuming script_dir.parent is the project root (e.g. DeBot/)
    # This makes module_path_for_db like "userbot/modules/file_name.py"
    module_path_for_db = str(download_path.relative_to(script_dir.parent))

    try:
        await event.client.download_media(reply_message, file=str(download_path)) # Use event.client
        console.print(f"[ADDMOD] - File {file_name} downloaded to {download_path} for account {current_account_id}", style="blue")

        # Module Registration
        db_module = await db_get_module(module_name=module_name_from_file)
        if db_module is None:
            console.print(f"[ADDMOD] - Module {module_name_from_file} not in DB, adding...", style="blue")
            # Pass description if available from module, else default
            module_id = await db_add_module(
                module_name=module_name_from_file, 
                module_path=module_path_for_db, 
                description="Added via .addmod" 
            )
            if not module_id:
                await event.edit(f"❌ Не удалось зарегистрировать модуль {module_name_from_file} в базе данных.")
                if download_path.exists(): download_path.unlink() 
                return
            console.print(f"[ADDMOD] - Module {module_name_from_file} added to DB with ID {module_id} (context: account {current_account_id})", style="blue")
        else:
            module_id = db_module['module_id']
            console.print(f"[ADDMOD] - Module {module_name_from_file} already exists in DB with ID {module_id} (context: account {current_account_id})", style="blue")
            if db_module.get('module_path') != module_path_for_db:
                 console.print(f"[ADDMOD] - Warning: Module {module_name_from_file} path mismatch for account {current_account_id}. DB: {db_module.get('module_path')}, New: {module_path_for_db}", style="yellow")

        # Link to Account
        existing_link = await get_account_module(account_id=current_account_id, module_id=module_id) # Use current_account_id
        if existing_link and existing_link['is_active']:
            await event.edit(f"ℹ️ Модуль `{module_name_from_file}` уже активен для аккаунта ID {current_account_id}.")
        elif existing_link and not existing_link['is_active']: 
             await link_module_to_account(account_id=current_account_id, module_id=module_id, is_active=True) # Use current_account_id
             console.print(f"[ADDMOD] - Module {module_name_from_file} re-activated for account {current_account_id}", style="green")
        elif not existing_link:
            link_result = await link_module_to_account(account_id=current_account_id, module_id=module_id, is_active=True) # Use current_account_id
            if not link_result:
                await event.edit(f"❌ Не удалось связать модуль {module_name_from_file} с аккаунтом ID {current_account_id}.")
                return
            console.print(f"[ADDMOD] - Module {module_name_from_file} linked to account {current_account_id}", style="green")

        # Load the module dynamically
        import_name = module_path_for_db.replace(os.sep, ".").replace(".py", "")
        
        # Handle module already being in sys.modules (e.g. loaded by another account)
        if import_name in sys.modules and (current_account_id, module_name_from_file) in LOADED_MODULES_CACHE:
            module_obj = LOADED_MODULES_CACHE[(current_account_id, module_name_from_file)]
            console.print(f"[ADDMOD] - Module {import_name} already loaded and processed for account {current_account_id}. Ensuring active.", style="yellow")
        elif import_name in sys.modules: # Loaded by another account, but not yet for this one
            module_obj = sys.modules[import_name]
            console.print(f"[ADDMOD] - Module {import_name} was in sys.modules (likely by another account). Applying to account {current_account_id}.", style="yellow")
            # If module has a specific function to register handlers for a new client:
            if hasattr(module_obj, "register_handlers_on_client") and callable(module_obj.register_handlers_on_client):
                module_obj.register_handlers_on_client(event.client) # Pass current client
        else: # Module not in sys.modules yet
            spec = importlib.util.spec_from_file_location(import_name, module_path_for_db)
            if spec is None:
                await event.edit(f"❌ Не удалось загрузить спецификацию для {module_name_from_file} (account {current_account_id}).")
                return
            module_obj = importlib.util.module_from_spec(spec)
            sys.modules[import_name] = module_obj # Add to sys.modules before exec
            spec.loader.exec_module(module_obj)
        
        LOADED_MODULES_CACHE[(current_account_id, module_name_from_file)] = module_obj # Cache per account

        # Update account-specific help_info
        account_specific_help = GLOBAL_HELP_INFO.get(current_account_id, {})
        if hasattr(module_obj, "info") and isinstance(module_obj.info, ModuleInfo):
            module_info_instance = module_obj.info
            category = module_info_instance.category
            if category:
                if category not in account_specific_help: 
                    account_specific_help[category] = f"<b>➖ {category.capitalize()}</b>"
                
                for i in range(len(module_info_instance.patterns)):
                    pattern_text = module_info_instance.patterns[i].strip()
                    if not pattern_text: continue
                    desc_text = module_info_instance.descriptions[i].strip() if i < len(module_info_instance.descriptions) else "No description"
                    account_specific_help[category] += f"\n<code>{pattern_text}</code> -> <i>{convert_to_fancy_font(desc_text)}</i>"
            else:
                console.print(f"[ADDMOD] - Module {module_info_instance.name} has 'info' but no 'category'. Not added to help for account {current_account_id}.", style="yellow")
        else:
            console.print(f"[ADDMOD] - Module {module_name_from_file} has no 'info' attribute of type ModuleInfo. Not added to help for account {current_account_id}.", style="yellow")
        
        await event.edit(f"✅ Модуль `{module_name_from_file}` успешно добавлен и загружен для аккаунта ID {current_account_id}.")
        console.print(f"[ADDMOD] - Module {module_name_from_file} dynamically loaded for account {current_account_id}. Account-specific help updated.", style="green")

    except Exception as e:
        await event.edit(f"❌ Ошибка при добавлении модуля {module_name_from_file} для аккаунта {current_account_id}: {e}")
        console.print(f"[ADDMOD] - Error processing module {module_name_from_file} for account {current_account_id}: {e}", style="bold red")
        if 'download_path' in locals() and download_path.exists():
             pass 

async def delmod_handler(event): 
    # No direct change to GLOBAL_HELP_INFO here, as it's rebuilt by load_account_modules.
    # If a module is deleted, its help entries won't be added next time.
    global console, GLOBAL_HELP_INFO, LOADED_MODULES_CACHE 
    
    current_account_id = await get_account_id_from_client(event, ACTIVE_CLIENTS)
    if current_account_id is None:
        await event.edit("Internal error: Could not identify account for this client.")
        return

    module_name_to_delete = event.pattern_match.group(1)

    db_module = await db_get_module(module_name=module_name_to_delete)
    if not db_module:
        await event.edit(f"❌ Модуль `{module_name_to_delete}` не найден в базе данных.")
        return

    module_id = db_module['module_id']
    module_path_from_db = db_module.get('module_path') 
    import_name_to_delete = module_path_from_db.replace(os.sep, ".").replace(".py", "") if module_path_from_db else None

    unlinked = await unlink_module_from_account(account_id=current_account_id, module_id=module_id) # Use current_account_id

    if unlinked:
        console.print(f"[DELMOD] - Module {module_name_to_delete} (ID: {module_id}) unlinked for account {current_account_id}", style="green")
        
        if import_name_to_delete:
            handlers_to_remove = []
            for callback, event_builder_obj in event.client.list_event_handlers(): # Use event.client
                if hasattr(callback, '__module__') and callback.__module__ == import_name_to_delete:
                    handlers_to_remove.append((callback, event_builder_obj))
            
            if handlers_to_remove:
                for cb, eb in handlers_to_remove:
                    event.client.remove_event_handler(cb, eb) # Use event.client
                console.print(f"[DELMOD] - Attempted to remove {len(handlers_to_remove)} event handlers for {module_name_to_delete} from client of account {current_account_id}", style="yellow")
            else:
                console.print(f"[DELMOD] - No event handlers found with module path '{import_name_to_delete}' to remove for {module_name_to_delete} on client of account {current_account_id}.", style="yellow")
        else:
            console.print(f"[DELMOD] - No module path in DB for {module_name_to_delete}, cannot determine import name for handler removal (account {current_account_id}).", style="red")

        # Unload from LOADED_MODULES_CACHE for this specific account
        if (current_account_id, module_name_to_delete) in LOADED_MODULES_CACHE:
            del LOADED_MODULES_CACHE[(current_account_id, module_name_to_delete)]
            console.print(f"[DELMOD] - Module {module_name_to_delete} removed from LOADED_MODULES_CACHE for account {current_account_id}.", style="yellow")

        # Unload from sys.modules only if no other account is using it
        if import_name_to_delete and import_name_to_delete in sys.modules:
            is_used_by_other_accounts = False
            for (acc_id, mod_name), mod_obj in LOADED_MODULES_CACHE.items():
                # Check if the module object's __name__ (which is the import_name) is used by another account
                if mod_obj.__name__ == import_name_to_delete and acc_id != current_account_id : # Check acc_id too
                    is_used_by_other_accounts = True
                    break
            if not is_used_by_other_accounts:
                del sys.modules[import_name_to_delete]
                console.print(f"[DELMOD] - Module {import_name_to_delete} removed from sys.modules as no other active account uses it.", style="yellow")
            else:
                console.print(f"[DELMOD] - Module {import_name_to_delete} kept in sys.modules as other active accounts might be using it.", style="yellow")
        
        await event.edit(f"✅ Модуль `{module_name_to_delete}` был отвязан от вашего аккаунта (ID: {current_account_id}).")
    else:
        await event.edit(f"❌ Не удалось отвязать модуль `{module_name_to_delete}` от аккаунта ID {current_account_id}.")


async def help_commands_handler(event): 
    global GLOBAL_HELP_INFO, console 
    current_account_id = await get_account_id_from_client(event, ACTIVE_CLIENTS)
    if console: console.print(f"-> [.help] for account {current_account_id}")

    account_specific_help = GLOBAL_HELP_INFO.get(current_account_id, {}).copy() # Get a copy or default
    
    # Ensure default categories and static commands are present for display
    # These are now primarily populated by start_individual_client
    # Here, we ensure they are displayed correctly.
    if not account_specific_help: # If account_id was not in GLOBAL_HELP_INFO or its dict was empty
        account_specific_help["chat"] = "<b>➖ Chat</b>"
        account_specific_help["fun"] = "<b>➖ Fun</b>"
        account_specific_help["tools"] = "<b>➖ Tools</b>"
        
    # Add static commands to the 'tools' section for display if not already detailed by modules
    # This ensures core commands are always visible.
    # A more robust method would be to check if these exact lines are already there.
    static_tools_help = ""
    # Example of adding static commands; actual fancy font conversion should be handled if needed
    about_cmd_desc = convert_to_fancy_font("о юзᴇᴩбоᴛᴇ")
    addmod_cmd_desc = convert_to_fancy_font("добᴀʙиᴛь ʍодуᴧь (ᴩᴇᴨᴧᴀᴇʍ нᴀ ɸᴀйᴧ)")
    delmod_cmd_desc = convert_to_fancy_font("удᴀᴧиᴛь ʍодуᴧь")
    setproxy_cmd_desc1 = convert_to_fancy_font("настроить прокси (тип: http, socks4, socks5)")
    setproxy_cmd_desc2 = convert_to_fancy_font("очистить настройки прокси")


    static_tools_help += f"\n<code>.about</code> -> <i>{about_cmd_desc}</i>"
    static_tools_help += f"\n<code>.addmod</code> -> <i>{addmod_cmd_desc}</i>"
    static_tools_help += f"\n<code>.delmod</code> -> <i>{delmod_cmd_desc}</i>"
    static_tools_help += f"\n<code>.setproxy &lt;type&gt; &lt;ip&gt; &lt;port&gt; [user] [pass]</code> -> <i>{setproxy_cmd_desc1}</i>"
    static_tools_help += f"\n<code>.setproxy clear</code> -> <i>{setproxy_cmd_desc2}</i>"


    if "tools" in account_specific_help:
        # A simple check to avoid massive duplication. More sophisticated merging might be needed if modules use these exact patterns.
        if ".setproxy clear" not in account_specific_help["tools"]: # Check if the specific .setproxy line is absent
             # Check if only base category string exists, then append. Otherwise, might already have module commands.
            if account_specific_help["tools"] == "<b>➖ Tools</b>":
                account_specific_help["tools"] += static_tools_help
            else: # Modules already added to tools, ensure static commands are there.
                  # This simple append might not be ideal if order matters greatly or for avoiding duplicates.
                  # A better way would be for modules to not use the exact same pattern string.
                  account_specific_help["tools"] += static_tools_help # Appending, might need smarter merging
    else:
        account_specific_help["tools"] = f"<b>➖ Tools</b>{static_tools_help}"


    help_text_parts = [account_specific_help[cat] for cat in sorted(account_specific_help.keys()) if account_specific_help[cat].strip()]
    final_help_text = "\n\n".join(help_text_parts)
    
    # Check if only base categories are present (no modules added commands)
    is_empty_dynamic_help = True
    for category, content in account_specific_help.items():
        if content.replace(f"<b>➖ {category.capitalize()}</b>", "").strip(): # Check if there's more than just the header
            # Exclude static tools we just added for this check
            if category == "tools" and content.replace(f"<b>➖ {category.capitalize()}</b>", "").replace(static_tools_help, "").strip():
                is_empty_dynamic_help = False
                break
            elif category != "tools": # For other categories, any content beyond header means not empty
                is_empty_dynamic_help = False
                break
                
    if is_empty_dynamic_help and not final_help_text.strip().endswith(static_tools_help.strip()): # Also check if final text just contains static tools
         final_help_text = f"<i>Кастомные модули не загружены или информация помощи недоступна для аккаунта {current_account_id}.</i>\n\n" + final_help_text


    if not final_help_text.strip(): # Fallback if everything is empty
        final_help_text = f"<i>Информация помощи недоступна для аккаунта {current_account_id}.</i>"
    
    await event.client.edit_message(event.message, final_help_text, parse_mode="HTML")


async def about_command_handler(event): 
    global console
    current_account_id = await get_account_id_from_client(event, ACTIVE_CLIENTS)
    account_name_display = "Unknown" # Default
    if current_account_id:
        # Try to get account_name from db_manager if needed, or store in ACTIVE_CLIENTS value if preferred
        # For now, just using ID.
        account_name_display = f"ID: {current_account_id}"


    if console: console.print(f"-> [.about] for account {current_account_id}")
    await event.client.edit_message( # Use event.client
        event.message,
        f"""<b>😈 𝚄𝚜𝚎𝚛𝚋𝚘𝚝 𝚋𝚢: <a href="t.me/whynothacked">𝕯𝖊𝕮𝖔𝖉𝖊𝖉</a></b>
<b>Аккаунт:</b> <code>{account_name_display}</code>
<b>💻 𝚃𝚎𝚕𝚎𝚝𝚑𝚘𝚗:</b> <code>{telethon.__version__}</code>""",
        parse_mode="HTML",
    )

def register_event_handlers():
    global console
    if not ACTIVE_CLIENTS:
        if console: console.print("[MAIN] - No active clients found to register handlers for.", style="yellow")
        else: print("[MAIN] - No active clients found to register handlers for.")
        return

    registered_count = 0
    for client_id, client_instance in ACTIVE_CLIENTS.items():
        if not client_instance or not hasattr(client_instance, 'add_event_handler'):
            if console: console.print(f"[MAIN] - Invalid client instance for ID {client_id}. Skipping handler registration.", style="red")
            else: print(f"[MAIN] - Invalid client instance for ID {client_id}. Skipping handler registration.")
            continue

        # Ensure each handler function is correctly referenced
        client_instance.add_event_handler(addmod_handler, events.NewMessage(outgoing=True, pattern=r"^\.addmod$"))
        client_instance.add_event_handler(delmod_handler, events.NewMessage(outgoing=True, pattern=r"^\.delmod (\w+)$"))
        client_instance.add_event_handler(help_commands_handler, events.NewMessage(outgoing=True, pattern=r"^\.help$"))
        client_instance.add_event_handler(about_command_handler, events.NewMessage(outgoing=True, pattern=r"^\.about$"))
        client_instance.add_event_handler(setproxy_handler, events.NewMessage(outgoing=True, pattern=r"^\.setproxy(?:\s+([a-zA-Z0-9_.-]+)(?:\s+([a-zA-Z0-9_.-]+)\s+(\d+)(?:\s+([^\s]+))?(?:\s+([^\s]+))?)?)?$"))
        registered_count += 5 
    
    if console: console.print(f"[MAIN] - Registered {registered_count} event handlers across {len(ACTIVE_CLIENTS)} client(s).", style="green")
    else: print(f"[MAIN] - Registered {registered_count} event handlers across {len(ACTIVE_CLIENTS)} client(s).")


if __name__ == "__main__":
    console = Console() # Initialize console first
    os.system("cls") if os.name == "nt" else os.system("clear")
    console.print(text2art("DeBot", font="random", chr_ignore=True), style="cyan")
    time.sleep(0.5) # Reduced sleep
    console.print("\n                            coded by @whynothacked", style="yellow")
    time.sleep(0.5) # Reduced sleep
    console.print("\n            • Пропиши .help в любом чате для получения команд бота", style="red")
    time.sleep(0.5) # Reduced sleep
    console.print("\n                           ↓ Снизу будут логи", style="green")

    # Module loading is now handled by start_individual_client in __init__.py.
    console.print("[MAIN] - Userbot __main__ started. Client setup is handled by __init__.py.", style="bold green")
    console.print("[MAIN] - Event handlers will be registered once clients are active.", style="yellow")

    # The LOOP is started by __init__.py when it runs manage_clients().
    # We need to ensure register_event_handlers() is called *after* manage_clients() has
    # populated ACTIVE_CLIENTS and started individual client tasks.
    # A simple way is to schedule it on the already running loop from __init__.py.
    # If LOOP is not running, it means __init__.py's async logic hasn't run, which is an issue.
    
    if LOOP.is_running():
        # Schedule register_event_handlers to run soon.
        # This allows manage_clients (called from __init__) to complete its synchronous parts
        # and schedule its own async tasks (like starting clients) first.
        LOOP.call_soon(lambda: asyncio.ensure_future(register_event_handlers(), loop=LOOP))
        console.print("[MAIN] - Scheduled event handler registration on the running event loop.", style="blue")
    else:
        # This is less ideal, as __init__.py should have started the loop.
        # Running it here might mean manage_clients hasn't run yet.
        console.print("[MAIN] - LOOP is not running. Attempting to run register_event_handlers directly. This may indicate an issue with __init__.py's loop management.", style="bold red")
        LOOP.run_until_complete(register_event_handlers()) # Fallback, but investigate if this path is taken.


    # --- Scheduler Setup ---
    
async def setproxy_handler(event):
    global console
    current_account_id = await get_account_id_from_client(event, ACTIVE_CLIENTS)
    if current_account_id is None:
        await event.edit("Internal error: Could not identify account for this client.")
        return

    args = event.pattern_match.groups()
    proxy_type_arg = args[0]

    if not proxy_type_arg: 
        await event.edit("❌ Proxy type is required. Usage: `.setproxy <type|clear> [ip] [port] [user] [pass]`")
        return
        
    proxy_type_arg = proxy_type_arg.lower()

    if proxy_type_arg in ["none", "clear"]:
        try:
            success = await update_account_proxy_settings(current_account_id, None, None, None, None, None)
            if success:
                await event.edit("✅ Proxy settings cleared for this account. "
                                 "**Пожалуйста, перезапустите процесс бота для этого аккаунта (или весь бот), чтобы изменения вступили в силу.**")
            else:
                await event.edit("⚠️ Не удалось очистить настройки прокси. Аккаунт не найден или произошла ошибка БД.")
        except Exception as e:
            await event.edit(f"❌ Ошибка при очистке прокси: {e}")
            if console: console.print(f"[SEPROXY] Error clearing proxy for account {current_account_id}: {e}", style="bold red")
        return

    proxy_ip_arg = args[1]
    proxy_port_arg = args[2]
    proxy_user_arg = args[3] 
    proxy_pass_arg = args[4] 

    if not proxy_ip_arg or not proxy_port_arg: # Required if not clearing
        await event.edit("❌ IP-адрес и порт обязательны для этого типа прокси. Usage: `.setproxy <type> <ip> <port> [user] [pass]`")
        return

    if proxy_type_arg not in ['http', 'socks4', 'socks5']:
        await event.edit(f"❌ Неверный тип прокси: `{proxy_type_arg}`. Доступные типы: http, socks4, socks5, clear.")
        return

    try:
        port_int = int(proxy_port_arg)
        if not (0 < port_int < 65536):
             raise ValueError("Port out of range")
    except ValueError:
        await event.edit(f"❌ Неверный порт: `{proxy_port_arg}`. Порт должен быть числом от 1 до 65535.")
        return

    encrypted_username = encryption_manager.encrypt(proxy_user_arg.encode('utf-8')) if proxy_user_arg else None
    encrypted_password = encryption_manager.encrypt(proxy_pass_arg.encode('utf-8')) if proxy_pass_arg else None
    
    try:
        success = await update_account_proxy_settings(
            current_account_id, 
            proxy_type_arg, 
            proxy_ip_arg, 
            port_int, 
            encrypted_username, 
            encrypted_password
        )
        if success:
            await event.edit(f"✅ Настройки прокси обновлены для этого аккаунта: {proxy_type_arg}://{proxy_ip_arg}:{port_int}. "
                             "**Пожалуйста, перезапустите процесс бота для этого аккаунта (или весь бот), чтобы изменения вступили в силу.**")
        else:
            await event.edit("⚠️ Не удалось обновить настройки прокси. Аккаунт не найден или произошла ошибка БД.")
    except Exception as e:
        await event.edit(f"❌ Ошибка при обновлении прокси: {e}")
        if console: console.print(f"[SEPROXY] Error setting proxy for account {current_account_id}: {e}", style="bold red")

    # --- Scheduler Setup ---
    scheduler = AsyncIOScheduler(timezone="UTC") # Or your desired timezone
    scheduler.add_job(perform_garbage_collection, 'interval', minutes=60, id='gc_job')
    scheduler.start()
    console.print("-> [system] - Scheduled garbage collection every 60 minutes.", style="blue")
    # --- End Scheduler Setup ---

    try:
        LOOP.run_forever()
    except KeyboardInterrupt:
        console.print("\n[MAIN] - Userbot stopped by user (KeyboardInterrupt).", style="bold yellow")
    except Exception as e:
        console.print(f"\n[MAIN] - Userbot event loop stopped due to an error: {e}", style="bold red")
    finally:
        console.print("[MAIN] - Cleaning up and closing resources...", style="yellow")
        if 'scheduler' in locals() and scheduler.running:
            scheduler.shutdown()
            console.print("-> [system] - Garbage collection scheduler shut down.", style="blue")
        console.print("[MAIN] - Userbot shutdown complete.", style="bold green")
