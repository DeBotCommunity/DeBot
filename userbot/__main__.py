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

# Specific imports from userbot package & modules
from userbot import CLIENT, LOOP, help_info, CURRENT_ACCOUNT_ID, MODULE_FOLDER, ALPHABET
from userbot.src.module_info import ModuleInfo # Import the new class
from userbot.src.db_manager import (
    get_active_modules_for_account,
    add_module as db_add_module,
    get_module as db_get_module,
    link_module_to_account,
    unlink_module_from_account,
    get_account_module # To check if already linked
)

# Global console object, will be initialized in __main__
console: Console = None

async def perform_garbage_collection():
    gc.collect()
    if console: # Ensure console is available
        console.print("-> [system] - Performed scheduled garbage collection.", style="dim blue")
    else:
        print("-> [system] - Performed scheduled garbage collection (console not available).")

def convert_to_fancy_font(text):
    converted_text = [ALPHABET.get(char, char) for char in text.lower()]
    return "".join(converted_text)

LOADED_MODULES_CACHE = {} 

async def load_account_modules(current_help_info):
    global console # help_info is now passed as a parameter
    if CURRENT_ACCOUNT_ID is None:
        if console: console.print("[MODULES] - CRITICAL: CURRENT_ACCOUNT_ID is None. Cannot load modules.", style="bold red")
        else: print("[MODULES] - CRITICAL: CURRENT_ACCOUNT_ID is None. Cannot load modules.")
        return
    if not console:
        print("[MODULES] - Console not initialized for load_account_modules.")
        return

    console.print(f"[MODULES] - Loading modules for account_id: {CURRENT_ACCOUNT_ID}", style="yellow")
    try:
        active_modules = await get_active_modules_for_account(CURRENT_ACCOUNT_ID)
    except Exception as e:
        console.print(f"[MODULES] - Error fetching active modules from DB: {e}", style="bold red")
        return

    if not active_modules:
        console.print(f"[MODULES] - No active modules found for account {CURRENT_ACCOUNT_ID}.", style="yellow")
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
            if import_name in sys.modules:
                module_obj = sys.modules[import_name]
                console.print(f"[MODULES] - Module {module_name} (as {import_name}) already loaded. Using existing.", style="yellow")
            else:
                spec = importlib.util.spec_from_file_location(import_name, module_path)
                if spec is None:
                    console.print(f"[MODULES] - Failed to create spec for {module_name} from {module_path}", style="bold red")
                    continue
                module_obj = importlib.util.module_from_spec(spec)
                sys.modules[import_name] = module_obj
                spec.loader.exec_module(module_obj)
            
            LOADED_MODULES_CACHE[module_name] = module_obj
            console.print(f"[MODULES] - Successfully loaded module: {module_name} (as {import_name}) for account {CURRENT_ACCOUNT_ID}", style="bold green")
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
    
    console.print(f"[MODULES] - Total modules loaded for account {CURRENT_ACCOUNT_ID}: {loaded_count}/{len(active_modules)}", style="bold green")

# load_module_sortner function is removed.

@CLIENT.on(events.NewMessage(outgoing=True, pattern=r"^\.addmod$"))
async def addmod(event):
    global console, help_info, LOADED_MODULES_CACHE
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
        await CLIENT.download_media(reply_message, file=str(download_path))
        console.print(f"[ADDMOD] - File {file_name} downloaded to {download_path}", style="blue")

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
                if download_path.exists(): download_path.unlink() # Clean up downloaded file
                return
            console.print(f"[ADDMOD] - Module {module_name_from_file} added to DB with ID {module_id}", style="blue")
        else:
            module_id = db_module['module_id']
            console.print(f"[ADDMOD] - Module {module_name_from_file} already exists in DB with ID {module_id}", style="blue")
            # Potentially update path if it changed, though not typical for .addmod
            if db_module.get('module_path') != module_path_for_db:
                 console.print(f"[ADDMOD] - Warning: Module {module_name_from_file} path mismatch. DB: {db_module.get('module_path')}, New: {module_path_for_db}", style="yellow")
                 # Decide on update strategy if needed, for now, we use the existing db_module_id

        # Link to Account
        # Check if already linked
        existing_link = await get_account_module(account_id=CURRENT_ACCOUNT_ID, module_id=module_id)
        if existing_link and existing_link['is_active']:
            await event.edit(f"ℹ️ Модуль `{module_name_from_file}` уже активен для вашего аккаунта.")
            # Still try to load it if not in cache, or re-load.
        elif existing_link and not existing_link['is_active']: # Reactivating
             await link_module_to_account(account_id=CURRENT_ACCOUNT_ID, module_id=module_id, is_active=True)
             console.print(f"[ADDMOD] - Module {module_name_from_file} re-activated for account {CURRENT_ACCOUNT_ID}", style="green")
        elif not existing_link:
            link_result = await link_module_to_account(account_id=CURRENT_ACCOUNT_ID, module_id=module_id, is_active=True)
            if not link_result:
                await event.edit(f"❌ Не удалось связать модуль {module_name_from_file} с вашим аккаунтом.")
                # File is downloaded but not linked. User might need to manually remove or try again.
                return
            console.print(f"[ADDMOD] - Module {module_name_from_file} linked to account {CURRENT_ACCOUNT_ID}", style="green")


        # Load the module dynamically
        import_name = module_path_for_db.replace(os.sep, ".").replace(".py", "")
        
        if import_name in sys.modules: # If loaded by another account or previously
            del sys.modules[import_name] # Unload to ensure fresh load for this account's context if needed
            console.print(f"[ADDMOD] - Module {import_name} was already in sys.modules. Unloaded for fresh load.", style="yellow")

        spec = importlib.util.spec_from_file_location(import_name, module_path_for_db)
        if spec is None:
            await event.edit(f"❌ Не удалось загрузить спецификацию для {module_name_from_file}.")
            return
        
        module_obj = importlib.util.module_from_spec(spec)
        sys.modules[import_name] = module_obj # Important: add to sys.modules before exec
        spec.loader.exec_module(module_obj)
        LOADED_MODULES_CACHE[module_name_from_file] = module_obj # Cache it

        # Update help_info
        if hasattr(module_obj, "info") and isinstance(module_obj.info, ModuleInfo):
            module_info_instance = module_obj.info
            category = module_info_instance.category
            if category:
                if category not in help_info: # addmod still uses global help_info
                    help_info[category] = f"<b>➖ {category.capitalize()}</b>"
                
                for i in range(len(module_info_instance.patterns)):
                    pattern_text = module_info_instance.patterns[i].strip()
                    if not pattern_text: continue
                    desc_text = module_info_instance.descriptions[i].strip() if i < len(module_info_instance.descriptions) else "No description"
                    help_info[category] += f"\n<code>{pattern_text}</code> -> <i>{convert_to_fancy_font(desc_text)}</i>"
            else:
                console.print(f"[ADDMOD] - Module {module_info_instance.name} has 'info' but no 'category'. Not added to help.", style="yellow")
        else:
            console.print(f"[ADDMOD] - Module {module_name_from_file} has no 'info' attribute of type ModuleInfo. Not added to help.", style="yellow")
        
        await event.edit(f"✅ Модуль `{module_name_from_file}` успешно добавлен и загружен для вашего аккаунта.")
        console.print(f"[ADDMOD] - Module {module_name_from_file} dynamically loaded and help_info updated.", style="green")

    except Exception as e:
        await event.edit(f"❌ Ошибка при добавлении модуля {module_name_from_file}: {e}")
        console.print(f"[ADDMOD] - Error processing module {module_name_from_file}: {e}", style="bold red")
        # Clean up if file was downloaded but failed later
        if 'download_path' in locals() and download_path.exists():
             # This might be too aggressive if module was meant for other accounts.
             # For now, assume .addmod is per-user action and file can be removed on user's error.
             # download_path.unlink() 
             pass


@CLIENT.on(events.NewMessage(outgoing=True, pattern=r"^\.delmod (\w+)$"))
async def delmod(event):
    global console, help_info, LOADED_MODULES_CACHE
    module_name_to_delete = event.pattern_match.group(1)

    if CURRENT_ACCOUNT_ID is None:
        await event.edit("❌ Не удалось определить текущий аккаунт.")
        return

    db_module = await db_get_module(module_name=module_name_to_delete)
    if not db_module:
        await event.edit(f"❌ Модуль `{module_name_to_delete}` не найден в базе данных.")
        return

    module_id = db_module['module_id']
    module_path_from_db = db_module.get('module_path') # e.g., userbot/modules/mod.py
    import_name_to_delete = module_path_from_db.replace(os.sep, ".").replace(".py", "") if module_path_from_db else None

    unlinked = await unlink_module_from_account(account_id=CURRENT_ACCOUNT_ID, module_id=module_id)

    if unlinked:
        console.print(f"[DELMOD] - Module {module_name_to_delete} (ID: {module_id}) unlinked for account {CURRENT_ACCOUNT_ID}", style="green")
        
        # Attempt to remove event handlers
        # This is best-effort. A more robust system would involve modules unregistering themselves.
        if import_name_to_delete:
            handlers_to_remove = []
            for callback, event_builder_obj in CLIENT.list_event_handlers():
                # Check callback.__module__ which should match the import_name
                if hasattr(callback, '__module__') and callback.__module__ == import_name_to_delete:
                    handlers_to_remove.append((callback, event_builder_obj)) # Store original tuple if that's what remove_event_handler expects
            
            if handlers_to_remove:
                for cb, eb in handlers_to_remove:
                    CLIENT.remove_event_handler(cb, eb) # Pass both callback and event
                console.print(f"[DELMOD] - Attempted to remove {len(handlers_to_remove)} event handlers for {module_name_to_delete}", style="yellow")
            else:
                console.print(f"[DELMOD] - No event handlers found with module path '{import_name_to_delete}' to remove for {module_name_to_delete}.", style="yellow")
        else:
            console.print(f"[DELMOD] - No module path in DB for {module_name_to_delete}, cannot determine import name for handler removal.", style="red")


        # Unload from sys.modules and cache
        if import_name_to_delete in sys.modules:
            del sys.modules[import_name_to_delete]
            console.print(f"[DELMOD] - Module {import_name_to_delete} removed from sys.modules.", style="yellow")
        if module_name_to_delete in LOADED_MODULES_CACHE:
            del LOADED_MODULES_CACHE[module_name_to_delete]
            console.print(f"[DELMOD] - Module {module_name_to_delete} removed from LOADED_MODULES_CACHE.", style="yellow")
        
        # TODO: Remove from help_info. This is complex as it requires knowing the category and specific lines.
        # A simpler approach for now is to rebuild help_info on next .help or restart.
        # Or, if a module has a cleanup function, it could remove its own help entries.

        await event.edit(f"✅ Модуль `{module_name_to_delete}` был отвязан от вашего аккаунта. "
                         "Перезапуск бота может потребоваться для полного удаления обработчиков событий и очистки команд помощи.")
    else:
        await event.edit(f"❌ Не удалось отвязать модуль `{module_name_to_delete}`. Возможно, он не был привязан, или произошла ошибка.")


@CLIENT.on(events.NewMessage(outgoing=True, pattern=r"^\.help$"))
async def help_commands(event):
    global help_info, console
    if console: console.print("-> [.help]")
    if "chat" not in help_info: help_info["chat"] = "<b>➖ Chat</b>"
    if "fun" not in help_info: help_info["fun"] = "<b>➖ Fun</b>"
    if "tools" not in help_info: help_info["tools"] = "<b>➖ Tools</b>"
    help_text_parts = [help_info[cat] for cat in sorted(help_info.keys()) if help_info[cat].strip()]
    final_help_text = "\n\n".join(help_text_parts)
    if not final_help_text.strip() or len(help_text_parts) == 0: # Check if parts is empty too
        final_help_text = "<i>Модули не загружены или информация помощи недоступна.</i>"
    await CLIENT.edit_message(event.message, final_help_text, parse_mode="HTML")


@CLIENT.on(events.NewMessage(outgoing=True, pattern=r"^\.about$"))
async def about_command(event):
    global console
    if console: console.print("-> [.about]")
    await CLIENT.edit_message(
        event.message,
        f"""<b>😈 𝚄𝚜𝚎𝚛𝚋𝚘𝚝 𝚋𝚢: <a href="t.me/whynothacked">𝕯𝖊𝕮𝖔𝖉𝖊𝖉</a></b>

<b>💻 𝚃𝚎𝚕𝚎𝚝𝚑𝚘𝚗:</b> <code>{telethon.__version__}</code>""",
        parse_mode="HTML",
    )


if __name__ == "__main__":
    console = Console()
    os.system("cls") if os.name == "nt" else os.system("clear")
    console.print(text2art("DeBot", font="random", chr_ignore=True), style="cyan")
    time.sleep(1)
    console.print("\n                            coded by @whynothacked", style="yellow")
    time.sleep(2)
    console.print("\n            • Пропиши .help в любом чате для получения команд бота", style="red")
    time.sleep(1)
    console.print("\n                           ↓ Снизу будут логи", style="green")

    if CURRENT_ACCOUNT_ID is not None:
        console.print(f"[MAIN] - Attempting to load modules for account: {CURRENT_ACCOUNT_ID}", style="yellow")
    else:
        console.print("[MAIN] - CRITICAL: CURRENT_ACCOUNT_ID is None at __main__ startup. Modules cannot be loaded.", style="bold red")

    try:
        if CURRENT_ACCOUNT_ID is not None:
             LOOP.run_until_complete(load_account_modules(help_info))
        else:
            console.print("[MAIN] - Skipping module loading as CURRENT_ACCOUNT_ID is not set.", style="bold red")
    except Exception as e:
        console.print(f"[MAIN] - Error during initial module loading: {e}", style="bold red")

    console.print("[MAIN] - Userbot setup complete. Running event loop forever.", style="bold green")
    
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
