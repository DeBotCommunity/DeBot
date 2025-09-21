import logging
from datetime import datetime, timezone
from typing import Optional, Tuple, Any

from telethon.sessions.abstract import Session
from telethon.crypto import AuthKey

import userbot.src.db_manager as db_manager
from userbot.src.db.session import get_db

logger: logging.Logger = logging.getLogger(__name__)

class DbSession(Session):
    """
    A Telethon session class that stores session data in a PostgreSQL database.
    This implementation correctly provides all the abstract methods and properties
    required by Telethon's base Session class.
    """

    def __init__(self, account_id: int):
        """
        Initializes the database-backed session.

        Args:
            account_id (int): The unique identifier for the account this session belongs to.
        """
        super().__init__()
        if not isinstance(account_id, int):
            raise ValueError("DbSession requires a valid integer account_id.")
            
        self.account_id: int = account_id
        self._auth_key: Optional[AuthKey] = None
        self._dc_id: int = 0
        self._server_address: Optional[str] = None
        self._port: int = 443
        self._takeout_id: Optional[int] = None

        self._pts: Optional[int] = None
        self._qts: Optional[int] = None
        self._date: Optional[int] = None
        self._seq: Optional[int] = None
        
    async def load(self) -> None:
        """
        Loads the session data for the current account_id from the database.
        """
        logger.debug(f"Attempting to load session for account_id: {self.account_id}")
        async with get_db() as db:
            session_data = await db_manager.get_session(db, self.account_id)

        if session_data:
            logger.info(f"Session data found for account_id: {self.account_id}")
            self._dc_id = session_data.dc_id
            self._server_address = session_data.server_address
            self._port = session_data.port
            
            auth_key_bytes = session_data.auth_key_data
            if auth_key_bytes:
                self._auth_key = AuthKey(data=bytes(auth_key_bytes))
            else:
                self._auth_key = None
            
            self._takeout_id = session_data.takeout_id
            self._pts = session_data.pts
            self._qts = session_data.qts
            self._date = session_data.date
            self._seq = session_data.seq
        else:
            logger.info(f"No session data found in DB for account_id: {self.account_id}. New login required.")

    async def save(self) -> None:
        """
        Saves the current session data to the database.
        This is called automatically by Telethon.
        """
        logger.debug(f"Attempting to save session for account_id: {self.account_id}")
        session_data = {
            "account_id": self.account_id,
            "dc_id": self._dc_id,
            "server_address": self._server_address,
            "port": self._port,
            "auth_key_data": self._auth_key.key if self._auth_key else None,
            "pts": self._pts,
            "qts": self._qts,
            "date": self._date,
            "seq": self._seq,
            "takeout_id": self._takeout_id,
        }
        async with get_db() as db:
            await db_manager.add_or_update_session(db, **session_data)
        logger.info(f"Session saved for account_id: {self.account_id}")
        
    async def delete(self) -> None:
        """Deletes the session for the current account from the database."""
        logger.info(f"Deleting session from DB for account_id: {self.account_id}")
        async with get_db() as db:
            await db_manager.delete_session(db, self.account_id)
        # Clear in-memory data
        self._auth_key = None
        self._dc_id = 0
    
    # --- Abstract Properties Implementation ---
    
    @property
    def dc_id(self) -> int:
        return self._dc_id

    @property
    def server_address(self) -> Optional[str]:
        return self._server_address

    @property
    def port(self) -> int:
        return self._port

    @property
    def auth_key(self) -> Optional[AuthKey]:
        return self._auth_key

    @auth_key.setter
    def auth_key(self, value: Optional[AuthKey]):
        self._auth_key = value

    @property
    def takeout_id(self) -> Optional[int]:
        return self._takeout_id

    @takeout_id.setter
    def takeout_id(self, value: Optional[int]):
        self._takeout_id = value

    # --- Abstract Methods Implementation ---

    def set_dc(self, dc_id: int, server_address: str, port: int):
        self._dc_id = dc_id
        self._server_address = server_address
        self._port = port

    def get_update_state(self, entity_id: int) -> Optional[Tuple[int, int, int, int, int]]:
        """Note: This implementation is global, not per-entity."""
        if self._pts is None:
            return None
        return self._pts, self._qts, self._date, self._seq, 0

    def set_update_state(self, entity_id: int, state: Any):
        """Note: This implementation is global, not per-entity."""
        if isinstance(state.date, datetime):
            date_ts = int(state.date.replace(tzinfo=timezone.utc).timestamp())
        else:
            date_ts = int(state.date)

        self._pts = state.pts
        self._qts = state.qts
        self._date = date_ts
        self._seq = state.seq
        
    async def close(self) -> None:
        """No action needed for DB sessions as the pool is managed globally."""
        pass

    # --- Deprecated/Legacy Abstract Methods (from older Telethon versions) ---
    # These might still be abstract in some versions, so we provide them.
    
    def get_update_states(self) -> List[Tuple[int, int, int, int, int, int]]:
        """
        Returns all update states.
        Since we store only one global state, we return it for the "self" user entity.
        The entity ID 0 is a placeholder for "self".
        """
        if self._pts is None:
            return []
        # entity_id, pts, qts, date, seq, unread_count
        return [(0, self._pts, self._qts, self._date, self._seq, 0)]
