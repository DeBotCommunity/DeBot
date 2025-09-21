import asyncio
import gc
import io
import logging
import subprocess
import sys
import shlex
from pathlib import Path
from typing import Dict, Any, List, Set, Optional

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from rich.console import Console
from telethon import events
from telethon.errors import SessionPasswordNeededError
from telethon.sessions import StringSession
from art import text2art

from userbot import (
    ACTIVE_CLIENTS, FAKE, TelegramClient,
    db_setup, manage_clients, GLOBAL_HELP_INFO
)
from userbot.src.config import (
    GC_INTERVAL_SECONDS, LOG_QUEUE_INTERVAL_SECONDS, LOG_QUEUE_BATCH_SIZE,
    TIMEZONE, LOG_ROTATION_ENABLED, LOG_RETENTION_DAYS, MODULE_UPDATE_INTERVAL_MINUTES
)
from userbot.src.db.session import get_db
import userbot.src.db_manager as db_manager
from userbot.src.log_handler import log_queue
from userbot.src.module_client import ModuleClient
from userbot.src.module_info import ModuleInfo
from userbot.src.module_parser import parse_module_metadata

# Suppress noisy APScheduler logs
logging.getLogger('apscheduler').setLevel(logging.WARNING)

console: Console = Console()
logger: logging.Logger = logging.getLogger(__name__)

async def process_log_queue():
    logs_to_process: List[Dict[str, Any]] = []
    while len(logs_to_process) < LOG_QUEUE_BATCH_SIZE and not log_queue.empty():
        try:
            logs_to_process.append(log_queue.get_nowait())
            log_queue.task_done()
        except asyncio.QueueEmpty:
            break
    if logs_to_process:
        try:
            async with get_db() as db_session:
                await db_manager.add_logs_bulk(db_session, logs_to_process)
        except Exception as e:
            logger.error(f"Failed to process log queue batch: {e}", exc_info=True)

async def rotate_logs_worker():
    logger.info("Running scheduled log rotation job...")
    async with get_db() as db:
        deleted_count = await db_manager.delete_old_logs(db, LOG_RETENTION_DAYS)
    logger.info(f"Log rotation complete. Deleted {deleted_count} old log entries.")

async def update_modules_worker():
    logger.info("Running scheduled module update job...")
    async with get_db() as db:
        modules_to_update = await db_manager.get_all_modules(db) # Simplified for now

    modules_dir = Path("userbot/modules")
    for module in modules_to_update:
        # Simplified metadata reading
        # In a real scenario, we'd parse the __update_url__ from the file
        pass # Placeholder for update logic

async def get_account_id_from_client(client) -> int | None:
    return next((acc_id for acc_id, c in ACTIVE_CLIENTS.items() if c == client), None)

async def load_account_modules(account_id: int, client_instance: TelegramClient, current_help_info: Dict[str, str]):
    console.print(f"[MODULES] - Loading modules for account_id: {account_id}", style="yellow")
    # Full implementation will be added here
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
    await event.edit("Запуск обновления модулей...")
    await update_modules_worker()
    await event.edit("Обновление модулей завершено.")

async def logs_handler(event: events.NewMessage.Event):
    subcommand = event.pattern_match.group(1)
    args_str = (event.pattern_match.group(2) or "").strip()
    
    if subcommand == "get":
        limit = 50
        level, source, as_file = None, None, False
        if args_str:
            try:
                # A simple arg parser
                args = shlex.split(args_str)
                if "--file" in args: as_file = True; args.remove("--file")
                if "--level" in args: level = args[args.index("--level")+1]; args.pop(args.index("--level")+1); args.remove("--level")
                if "--source" in args: source = args[args.index("--source")+1]; args.pop(args.index("--source")+1); args.remove("--source")
                if args: limit = int(args[0])
            except (ValueError, IndexError):
                await event.edit("Неверные аргументы для `.logs get`")
                return
        
        await event.edit(f"Получение последних {limit} логов...")
        async with get_db() as db:
            logs = await db_manager.get_logs_filtered(db, limit, level, source)

        if not logs:
            await event.edit("Логи не найдены по вашему запросу.")
            return

        output = "\n".join([f"[{log.timestamp.strftime('%Y-%m-%d %H:%M')}] [{log.level}] [{log.module_name or 'core'}] {log.message}" for log in logs])

        if as_file:
            with io.StringIO(output) as f:
                f.name = f"debot_logs_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
                await event.client.send_file(event.chat_id, f, caption=f"Логи DeBot ({len(logs)} записей)")
            await event.delete()
        else:
            # Send in chunks
            header = f"**Последние {len(logs)} логов:**\n\n"
            await event.edit(header + "```" + output[:3800] + "```")

    elif subcommand == "purge":
        async with event.client.conversation(event.chat_id) as conv:
            await conv.send_message("Вы уверены, что хотите **полностью** удалить все логи? Отправьте `да` для подтверждения.")
            response = await conv.get_response()
            if response.text.lower() == "да":
                async with get_db() as db:
                    count = await db_manager.purge_logs(db)
                await conv.send_message(f"Все {count} логов были удалены.")
            else:
                await conv.send_message("Очистка логов отменена.")
    else:
        await event.edit("Неизвестная подкоманда. Доступно: `get`, `purge`.")


# Account management handlers remain the same...
async def list_accounts_handler(event: events.NewMessage.Event): pass
async def add_account_handler(event: events.NewMessage.Event): pass
async def delete_account_handler(event: events.NewMessage.Event): pass
async def toggle_account_handler(event: events.NewMessage.Event): pass
async def set_lang_handler(event: events.NewMessage.Event): pass
async def help_commands_handler(event: events.NewMessage.Event): pass
async def about_command_handler(event: events.NewMessage.Event): pass


async def main():
    console.print(text2art("DeBot", font="random", chr_ignore=True), style="cyan")
    console.print("\n                            coded by @whynothacked", style="yellow")
    
    await db_setup()
    
    scheduler = AsyncIOScheduler(timezone=TIMEZONE)
    scheduler.add_job(gc.collect, 'interval', seconds=GC_INTERVAL_SECONDS, id='gc_job')
    scheduler.add_job(process_log_queue, 'interval', seconds=LOG_QUEUE_INTERVAL_SECONDS, id='log_queue_job')
    if LOG_ROTATION_ENABLED:
        scheduler.add_job(rotate_logs_worker, 'interval', hours=24, id='log_rotation_job')
    scheduler.add_job(update_modules_worker, 'interval', minutes=MODULE_UPDATE_INTERVAL_MINUTES, id='module_update_job')
    
    # Must be started after event loop is running
    scheduler.start()
    
    await manage_clients()
    
    logger.info("Userbot is running. Press Ctrl+C to stop.")
    await asyncio.Event().wait()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        console.print("\n[MAIN] - Userbot stopped by user.", style="bold yellow")
    except Exception as e:
        logger.critical(f"An unhandled error occurred in main: {e}", exc_info=True)
        sys.exit(1)
