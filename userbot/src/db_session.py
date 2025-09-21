import logging
from datetime import datetime, timezone
from typing import Optional, Tuple, Any, List

from telethon.sessions.abstract import Session
from telethon.crypto import AuthKey
from telethon.tl.types import PeerUser

import userbot.src.db_manager as db_manager
from userbot.src.db.session import get_db

logger: logging.Logger = logging.getLogger(__name__)

class DbSession(Session):
    """
    A Telethon session class that stores session data in a PostgreSQL database.
    """

    def __init__(self, account_id: int, self_user_id: Optional[int]):
        """
        Initializes the database-backed session.

        Args:
            account_id (int): The unique identifier for the account this session belongs to.
            self_user_id (Optional[int]): The Telegram user ID of the account holder.
        """
        super().__init__()
        if not isinstance(account_id, int):
            raise ValueError("DbSession requires a valid integer account_id.")
            
        self.account_id: int = account_id
        self._self_user_id: Optional[int] = self_user_id
        
        self._auth_key: Optional[AuthKey] = None
        self._dc_id: int = 0
        self._server_address: Optional[str] = None
        self._port: int = 443
        self._takeout_id: Optional[int] = None

        self._pts: Optional[int] = None
        self._qts: Optional[int] = None
        self._date: Optional[int] = None
        self._seq: Optional[int] = None

    @classmethod
    async def create(cls, account_id: int) -> "DbSession":
        """
        Asynchronously creates and pre-loads a DbSession instance.
        This factory method is used to fetch necessary data like the user_telegram_id
        before the synchronous parts of the session are accessed by Telethon.

        Args:
            account_id (int): The unique identifier for the account.

        Returns:
            DbSession: A new instance of DbSession.
        """
        self_user_id: Optional[int] = None
        async with get_db() as db:
            account = await db_manager.get_account_by_id(db, account_id)
            if account:
                self_user_id = account.user_telegram_id
        return cls(account_id, self_user_id)
        
    async def load(self) -> None:
        """Loads the session data for the current account_id from the database."""
        logger.debug(f"Attempting to load session for account_id: {self.account_id}")
        async with get_db() as db:
            session_data = await db_manager.get_session(db, self.account_id)

        if session_data:
            logger.info(f"Session data found for account_id: {self.account_id}")
            self._dc_id = session_data.dc_id
            self._server_address = session_data.server_address
            self._port = session_data.port
            self._auth_key = AuthKey(data=bytes(session_data.auth_key_data)) if session_data.auth_key_data else None
            self._takeout_id = session_data.takeout_id
            self._pts = session_data.pts
            self._qts = session_data.qts
            self._date = session_data.date
            self._seq = session_data.seq
        else:
            logger.info(f"No session data in DB for account_id: {self.account_id}. New login required.")

    async def save(self) -> None:
        """Saves the current session data to the database."""
        session_data = {
            "account_id": self.account_id, "dc_id": self._dc_id,
            "server_address": self._server_address, "port": self._port,
            "auth_key_data": self._auth_key.key if self._auth_key else None,
            "pts": self._pts, "qts": self._qts, "date": self._date,
            "seq": self._seq, "takeout_id": self._takeout_id,
        }
        async with get_db() as db:
            await db_manager.add_or_update_session(db, **session_data)
        logger.info(f"Session saved for account_id: {self.account_id}")
        
    async def delete(self) -> None:
        """Deletes the session for the current account from the database."""
        async with get_db() as db:
            await db_manager.delete_session(db, self.account_id)
        self._auth_key = None; self._dc_id = 0
    
    @property
    def dc_id(self) -> int: return self._dc_id
    @property
    def server_address(self) -> Optional[str]: return self._server_address
    @property
    def port(self) -> int: return self._port
    @property
    def auth_key(self) -> Optional[AuthKey]: return self._auth_key
    @auth_key.setter
    def auth_key(self, value: Optional[AuthKey]): self._auth_key = value
    @property
    def takeout_id(self) -> Optional[int]: return self._takeout_id
    @takeout_id.setter
    def takeout_id(self, value: Optional[int]): self._takeout_id = value

    def set_dc(self, dc_id: int, server_address: str, port: int):
        self._dc_id, self._server_address, self._port = dc_id, server_address, port

    def get_update_state(self, entity_id: int) -> Optional[Tuple[int, int, int, int, int]]:
        if self._pts is None: return None
        return self._pts, self._qts, self._date, self._seq, 0

    def set_update_state(self, entity_id: int, state: Any):
        if isinstance(state.date, datetime):
            date_ts = int(state.date.replace(tzinfo=timezone.utc).timestamp())
        else:
            date_ts = int(state.date)
        self._pts, self._qts, self._date, self._seq = state.pts, state.qts, date_ts, state.seq
        
    async def close(self) -> None: pass

    def get_update_states(self) -> List[Tuple[int, int, int, int, int, int]]:
        if self._pts is None: return []
        return [(0, self._pts, self._qts, self._date, self._seq, 0)]

    def process_entities(self, tlo: object) -> None: pass

    def get_input_entity(self, key: Any) -> Any:
        """
        Returns the input entity for the current user if key is 0.
        This is crucial for the client to know "who it is" upon startup.
        """
        if key == 0 and self._self_user_id is not None:
            return PeerUser(self._self_user_id)
        raise KeyError("Entity not found in DbSession cache (caching is not implemented for other entities).")

    def cache_file(self, md5_digest: bytes, file_size: int, instance: Any) -> None: pass

    def get_file(self, md5_digest: bytes, file_size: int, exact: bool = True) -> Optional[Any]:
        return None
