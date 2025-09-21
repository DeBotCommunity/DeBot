import asyncio
import gc
import logging
import sys
from typing import Dict, Any

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from rich.console import Console
from art import text2art

from userbot import (
    db_setup, manage_clients
)
from userbot.src.config import GC_INTERVAL_SECONDS, LOG_QUEUE_INTERVAL_SECONDS, TIMEZONE
from userbot.src.db.session import get_db
import userbot.src.db_manager as db_manager
from userbot.src.log_handler import log_queue

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


async def main():
    """The main entry point for the userbot."""
    console.print(text2art("DeBot", font="random", chr_ignore=True), style="cyan")
    console.print("\n                            coded by @whynothacked", style="yellow")
    
    await db_setup()
    
    scheduler = AsyncIOScheduler(timezone=TIMEZONE)
    scheduler.add_job(gc.collect, 'interval', seconds=GC_INTERVAL_SECONDS, id='gc_job')
    scheduler.add_job(process_log_queue, 'interval', seconds=LOG_QUEUE_INTERVAL_SECONDS, id='log_queue_job')
    scheduler.start()
    
    console.print(f"-> [system] - GC scheduled every {GC_INTERVAL_SECONDS} seconds.", style="blue")
    console.print(f"-> [system] - Log queue processing scheduled every {LOG_QUEUE_INTERVAL_SECONDS} seconds.", style="blue")

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
