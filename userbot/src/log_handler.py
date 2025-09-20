import logging
import asyncio
from typing import Optional

from userbot.src.db_manager import add_log

class DBLogHandler(logging.Handler):
    """
    A custom logging handler that writes log records to the database.
    """
    def __init__(self, level: int = logging.NOTSET) -> None:
        """
        Initializes the database log handler.

        Args:
            level (int): The minimum logging level for this handler.
        """
        super().__init__(level)

    def emit(self, record: logging.LogRecord) -> None:
        """
        Writes a log record to the database.

        This method is called by the logging framework for each log message.
        It schedules the database write operation on the running event loop.

        Args:
            record (logging.LogRecord): The log record to be processed.
        """
        # We need to get the running event loop to schedule our async db call
        try:
            loop: asyncio.AbstractEventLoop = asyncio.get_running_loop()
            # Default values for account_id and module_name
            account_id: Optional[int] = getattr(record, 'account_id', None)
            module_name: Optional[str] = getattr(record, 'module_name', None)

            # Fire and forget: schedule the coroutine to run on the loop
            asyncio.ensure_future(add_log(
                level=record.levelname,
                message=self.format(record),
                account_id=account_id,
                module_name=module_name
            ), loop=loop)
        except RuntimeError:
            # This can happen if logging occurs when no event loop is running.
            # In this case, we can't log to the DB.
            # We can print to stderr as a fallback for critical logs.
            if record.levelno >= logging.ERROR:
                print(f"CRITICAL [DBLogHandler-Fallback]: Could not log to DB (no running loop): {self.format(record)}")
        except Exception:
            # Fallback for any other error during logging to prevent crashes.
            print(f"CRITICAL [DBLogHandler-Fallback]: An unexpected error occurred in emit: {self.format(record)}")
