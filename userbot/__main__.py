import asyncio
import gc
import logging
import sys

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from rich.console import Console
from art import text2art

from userbot import (
    db_setup, manage_clients
)
from userbot.core.config import GC_INTERVAL_SECONDS, LOG_QUEUE_INTERVAL_SECONDS, TIMEZONE, LOG_ROTATION_ENABLED, LOG_RETENTION_DAYS
from userbot.db.session import get_db
from userbot.db import db_manager
from userbot.core.log_handler import log_queue

# Suppress noisy APScheduler logs
logging.getLogger('apscheduler').setLevel(logging.WARNING)

console: Console = Console()
logger: logging.Logger = logging.getLogger(__name__)

async def process_log_queue():
    """Periodically processes logs from the queue and writes them to the DB."""
    logs_to_process = []
    
    while not log_queue.empty():
        try:
            log_item = log_queue.get_nowait()
            logs_to_process.append(log_item)
            log_queue.task_done()
        except asyncio.QueueEmpty:
            break
            
    if logs_to_process:
        try:
            async with get_db() as db_session:
                await db_manager.add_logs_bulk(db_session, logs_to_process)
        except Exception as e:
            logger.error(f"Failed to process log queue batch: {e}", exc_info=True)

async def run_log_rotation():
    """Periodically deletes old logs from the database if rotation is enabled."""
    if not LOG_ROTATION_ENABLED:
        return
    
    logger.info(f"Running scheduled log rotation. Deleting logs older than {LOG_RETENTION_DAYS} days.")
    try:
        async with get_db() as db_session:
            deleted_count = await db_manager.delete_old_logs(db_session, LOG_RETENTION_DAYS)
        logger.info(f"Log rotation complete. Deleted {deleted_count} old log entries.")
    except Exception as e:
        logger.error(f"An error occurred during scheduled log rotation: {e}", exc_info=True)


async def main():
    """The main entry point for the userbot."""
    console.print(text2art("DeBot", font="random", chr_ignore=True), style="cyan")
    console.print("\n                            coded by @whynothacked", style="yellow")
    
    await db_setup()
    
    scheduler = AsyncIOScheduler(timezone=TIMEZONE)
    scheduler.add_job(gc.collect, 'interval', seconds=GC_INTERVAL_SECONDS, id='gc_job')
    scheduler.add_job(process_log_queue, 'interval', seconds=LOG_QUEUE_INTERVAL_SECONDS, id='log_queue_job')
    scheduler.add_job(run_log_rotation, 'interval', hours=24, id='log_rotation_job')
    scheduler.start()
    
    console.print(f"-> [system] - GC scheduled every {GC_INTERVAL_SECONDS} seconds.", style="blue")
    console.print(f"-> [system] - Log queue processing scheduled every {LOG_QUEUE_INTERVAL_SECONDS} seconds.", style="blue")
    if LOG_ROTATION_ENABLED:
        console.print(f"-> [system] - Log rotation scheduled every 24 hours (retention: {LOG_RETENTION_DAYS} days).", style="blue")

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
