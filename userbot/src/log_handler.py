import logging
import asyncio
from typing import Optional, Dict, Any

# A simple, thread-safe in-memory queue for log records.
# asyncio.Queue is used because the consumer (writer) is async.
log_queue: asyncio.Queue = asyncio.Queue()

class DBLogHandler(logging.Handler):
    """
    A custom logging handler that puts log records into an async queue.
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
        Puts a log record into the in-memory queue.

        This operation is non-blocking and safe to call from synchronous code.

        Args:
            record (logging.LogRecord): The log record to be processed.
        """
        try:
            log_entry: Dict[str, Any] = {
                'level': record.levelname,
                'message': self.format(record),
                'account_id': getattr(record, 'account_id', None),
                'module_name': getattr(record, 'module_name', None)
            }
            # put_nowait is a non-blocking call, safe for sync contexts.
            log_queue.put_nowait(log_entry)
        except asyncio.QueueFull:
            # This should rarely happen with a default-sized queue.
            # A fallback print is better than losing the log.
            print(f"CRITICAL [DBLogHandler-Fallback]: Log queue is full. Dropping log: {self.format(record)}")
        except Exception:
            # Broad exception to prevent any logging-related crash.
            print(f"CRITICAL [DBLogHandler-Fallback]: An unexpected error occurred in emit: {self.format(record)}")
