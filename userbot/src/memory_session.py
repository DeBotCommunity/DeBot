import io
import sqlite3
from typing import Optional

from telethon.sessions.sqlite import SQLiteSession

class MemorySession(SQLiteSession):
    """
    A Telethon session class that operates on an in-memory SQLite database.

    This session is initialized with the raw bytes of a session file and
    uses an in-memory database, avoiding disk I/O during runtime.
    """
    def __init__(self, session_bytes: Optional[bytes] = None) -> None:
        """
        Initializes the in-memory session.

        Args:
            session_bytes (Optional[bytes]): The raw bytes of a Telethon
                .session file to be loaded into memory. If None, a new
                in-memory session will be created.
        """
        super().__init__('memory_session')  # Dummy name, not used for file path
        self._conn: Optional[sqlite3.Connection] = None
        self._session_bytes: Optional[bytes] = session_bytes

    def _connect(self) -> None:
        """
        Creates a connection to an in-memory SQLite database.
        
        If initial session bytes were provided, this method loads them into
        the in-memory database.
        """
        self._conn = sqlite3.connect(':memory:')
        if self._session_bytes:
            # Use iterdump to replicate the on-disk database in memory
            # This is more robust than trying to load from a BytesIO object
            temp_conn: sqlite3.Connection = sqlite3.connect(':memory:')
            temp_conn.executescript(self._session_bytes.decode('utf-8'))
            for line in temp_conn.iterdump():
                if line not in ('BEGIN;', 'COMMIT;'): # let python handle transactions
                    self._conn.execute(line)
            temp_conn.close()
        
        # Connection is now live, create tables if they don't exist
        self._conn.execute("select name from sqlite_master where type='table' and name='sessions'")
        if self._conn.fetchone():
            return # Tables already exist

        # If not, create them
        self._create_table_and_indices()

    def save(self) -> bytes:
        """
        Saves the current state of the in-memory database to bytes.

        Returns:
            bytes: The content of the in-memory session database as bytes,
                   encoded in UTF-8.
        """
        if not self._conn:
            return b''

        # iterdump() is the canonical way to serialize a SQLite DB
        script: str = '\n'.join(self._conn.iterdump())
        return script.encode('utf-8')
