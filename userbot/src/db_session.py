import asyncio
import ipaddress
from datetime import datetime, timezone
from typing import Optional, Tuple, Any # Added Any for state

from telethon.sessions.abstract import Session
from telethon.crypto import AuthKey
# InputPhoto, InputDocument might be needed if we store more complex entities later
from telethon.tl.types import InputPhoto, InputDocument, PeerUser, PeerChat, PeerChannel 

# Assuming db_manager and config will be available in the path
# For now, direct imports; adjust if circular dependencies or structure issues arise
import userbot.src.db_manager as db_manager
# import userbot.src.config as config # Not directly used in this file yet.

# Logger setup (basic for now, can be integrated with a global logger)
import logging
logger = logging.getLogger(__name__)
# Basic config if no handlers are present, good for standalone testing/dev
if not logger.handlers:
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')


class DbSession(Session):
    """
    A Telethon session class that stores session data in a PostgreSQL database
    via the db_manager. This session stores individual fields rather than a single session string.
    """

    def __init__(self, account_id: int):
        super().__init__()
        if not isinstance(account_id, int):
            # This is a programming error, DbSession must be tied to an account.
            logger.error("DbSession initialized without a valid integer account_id.")
            raise ValueError("DbSession requires a valid integer account_id.")
            
        self.account_id: int = account_id
        self._auth_key: Optional[AuthKey] = None
        self._dc_id: int = 0 # Default DC, Telethon will determine the correct one.
        self._server_address: Optional[str] = None
        self._port: int = 443 # Default Telegram port
        self._takeout_id: Optional[int] = None

        # Fields for update state (pts, qts, date, seq)
        self._pts: Optional[int] = None
        self._qts: Optional[int] = None
        self._date: Optional[int] = None # Store as Unix timestamp (integer)
        self._seq: Optional[int] = None
        
        logger.debug(f"DbSession initialized for account_id: {self.account_id}")

    async def load(self):
        """
        Loads the session data for the current account_id from the database.
        This method is called by Telethon when the client starts.
        """
        logger.debug(f"Attempting to load session for account_id: {self.account_id}")
        session_data = await db_manager.get_session(self.account_id)

        if session_data:
            logger.info(f"Session data found for account_id: {self.account_id}")
            self._dc_id = session_data.get('dc_id', 0) # dc_id is a column name
            self._server_address = session_data.get('server_address')
            self._port = session_data.get('port', 443)
            
            auth_key_bytes = session_data.get('auth_key_data')
            if auth_key_bytes:
                self._auth_key = AuthKey(data=bytes(auth_key_bytes)) # Ensure it's bytes
                logger.debug(f"AuthKey loaded for account_id: {self.account_id}")
            else:
                self._auth_key = None
                logger.debug(f"No AuthKey found in DB for account_id: {self.account_id}")
            
            self._takeout_id = session_data.get('takeout_id')

            # Load update state fields
            self._pts = session_data.get('pts')
            self._qts = session_data.get('qts')
            self._date = session_data.get('date') # Stored as Unix timestamp
            self._seq = session_data.get('seq')
            logger.debug(f"Update state loaded: pts={self._pts}, qts={self._qts}, date={self._date}, seq={self._seq} for account_id: {self.account_id}")
        else:
            logger.info(f"No session data found in DB for account_id: {self.account_id}. New login likely required.")
            # Telethon will proceed with new login flow if auth_key is None

    async def save(self):
        """
        Saves the current session data to the database.
        This method is called by Telethon when session data changes.
        """
        if self._auth_key is None:
            # Usually, Telethon doesn't save if there's no auth_key (e.g., before login)
            # but if it does, we should ensure we don't try to access .key on None.
            logger.debug(f"Save called for account_id: {self.account_id}, but no auth_key present. Skipping save of key.")
            auth_key_data = None
        else:
            auth_key_data = self._auth_key.key
        
        # Ensure self._date is an integer timestamp. set_update_state should handle conversion.
        date_to_save = self._date
        if isinstance(self._date, datetime): # Should not happen if set_update_state is correct
            logger.warning(f"self._date is a datetime object during save for account {self.account_id}. Converting to timestamp. This indicates a potential issue in set_update_state or direct manipulation.")
            date_to_save = int(self._date.replace(tzinfo=timezone.utc).timestamp())

        logger.debug(f"Attempting to save session for account_id: {self.account_id}. DC: {self._dc_id}, AuthKey set: {self._auth_key is not None}")
        await db_manager.add_session(
            account_id=self.account_id,
            dc_id=self._dc_id,
            server_address=self._server_address,
            port=self._port,
            auth_key_data=auth_key_data,
            pts=self._pts,
            qts=self._qts,
            date=date_to_save, # Pass the integer timestamp
            seq=self._seq,
            takeout_id=self._takeout_id
        )
        logger.info(f"Session saved for account_id: {self.account_id}")

    def set_dc(self, dc_id: int, server_address: str, port: int):
        logger.debug(f"Setting DC for account_id {self.account_id}: dc_id={dc_id}, addr={server_address}, port={port}")
        self._dc_id = dc_id
        self._server_address = server_address
        self._port = port
        # Telethon typically calls .save() on its own after this if auth_key is also set.

    def get_dc(self) -> Tuple[int, Optional[str], int]: # server_address can be None initially
        return self._dc_id, self._server_address, self._port

    def set_auth_key(self, auth_key: Optional[AuthKey]): # Can be set to None on logout
        logger.debug(f"Setting AuthKey for account_id {self.account_id}. Key is {'None' if auth_key is None else 'Present'}")
        self._auth_key = auth_key
        # Telethon calls .save()

    def get_auth_key(self) -> Optional[AuthKey]:
        return self._auth_key

    async def delete(self):
        """
        Deletes the session for the current account_id from the database.
        Called when logging out (client.log_out()).
        """
        logger.info(f"Deleting session from DB for account_id: {self.account_id}")
        await db_manager.delete_session(self.account_id)
        # Clear in-memory session data as well
        self._auth_key = None
        self._dc_id = 0
        self._server_address = None
        self._port = 443
        self._takeout_id = None
        self._pts = None
        self._qts = None
        self._date = None
        self._seq = None
        logger.info(f"In-memory session cleared for account_id: {self.account_id} after deletion.")

    # --- Update State Methods ---
    def get_update_state(self) -> Optional[Tuple[int, int, int, int, int]]: # dc_id, pts, qts, date, seq
        """
        Returns the current update state (dc_id, pts, qts, date as timestamp, seq).
        Telethon's `UpdateState` namedtuple expects `date` as `datetime`, but the session methods
        `get_update_state` and `set_update_state` use raw tuples/objects.
        The `date` field in the database and in `self._date` is an integer (Unix timestamp).
        """
        if self._pts is None or self._qts is None or self._date is None or self._seq is None:
            logger.debug(f"get_update_state called for account {self.account_id}, but state is not fully set. Returning None.")
            return None
        
        # self._date is already an integer timestamp
        logger.debug(f"Getting update state for account {self.account_id}: dc_id={self._dc_id}, pts={self._pts}, qts={self._qts}, date_ts={self._date}, seq={self._seq}")
        return self._dc_id, self._pts, self._qts, self._date, self._seq

    def set_update_state(self, state: Any): # state is an UpdateState namedtuple from Telethon
        """
        Sets the update state. Telethon provides `state` object (UpdateState namedtuple)
        where `state.date` is a `datetime` object. This needs to be converted to a
        Unix timestamp (integer) for storage.
        """
        if state is None: # Should not happen based on Telethon's usage
            logger.warning(f"set_update_state called with None for account {self.account_id}")
            return

        # Assuming state has attributes pts, qts, date, seq.
        # state.date from Telethon is a datetime object. Convert to UTC timestamp.
        if isinstance(state.date, datetime):
            date_ts = int(state.date.replace(tzinfo=timezone.utc).timestamp())
        else: # If it's already a timestamp (e.g. from an older session type or manual call)
            date_ts = int(state.date)

        logger.debug(f"Setting update state for account {self.account_id}: pts={state.pts}, qts={state.qts}, date_dt={state.date} (ts={date_ts}), seq={state.seq}")
        self._pts = state.pts
        self._qts = state.qts
        self._date = date_ts # Store as integer timestamp
        self._seq = state.seq
        # self._dc_id = state.dc_id # dc_id is part of the tuple from get_update_state, but not directly set on state object by Telethon this way.
                                  # It's managed by set_dc.
        # Telethon calls .save() automatically.

    # --- Takeout ID ---
    @property
    def takeout_id(self) -> Optional[int]:
        return self._takeout_id

    @takeout_id.setter
    def takeout_id(self, value: Optional[int]):
        if self._takeout_id != value:
            logger.debug(f"Setting takeout_id for account {self.account_id}: {value}")
            self._takeout_id = value
            # Telethon usually handles saving when this is set during takeout process.
            # If manual setting, ensure save is called:
            # asyncio.create_task(self.save()) # if save needs to be forced

    # --- Minimal/No-op Methods for File/Entity Handling ---
    def list_files(self) -> list: # type: ignore[override]
        logger.debug(f"list_files called for account {self.account_id}, returning empty list.")
        return []

    def get_file(self, md5_digest: bytes, file_type: int) -> Optional[Tuple[bytes, Optional[Any]]]: # type: ignore[override]
        # Parameters adjusted to match telethon.sessions.abstract.Session.get_file
        logger.debug(f"get_file called for account {self.account_id}, md5: {md5_digest.hex()}, type: {file_type}. Returning None.")
        return None

    def cache_file(self, md5_digest: bytes, file_type: int, data: bytes, name: Optional[str] = None):
        # Parameters adjusted to match telethon.sessions.abstract.Session.cache_file
        logger.debug(f"cache_file called for account {self.account_id}, md5: {md5_digest.hex()}, type: {file_type}. Doing nothing.")
        pass 

    def process_entities(self, tlo: object):
        logger.debug(f"process_entities called for account {self.account_id}. No entity caching implemented.")
        pass

    def get_input_entity(self, key: object) -> object: # type: ignore[override]
        logger.debug(f"get_input_entity called for account {self.account_id}, key: {key}. Raising KeyError.")
        raise KeyError("Entity not found in DbSession cache (caching not implemented).")

    def _get_addr_port(self, test_mode: bool) -> Tuple[Optional[str], int]: # type: ignore[override]
        # Test mode can imply different DCs, but we just return what's set.
        logger.debug(f"get_addr_port called for account {self.account_id}. Test mode: {test_mode}. Returning: {self._server_address}, {self._port}")
        return self._server_address, self._port

    async def close(self):
        logger.debug(f"DbSession.close() called for account {self.account_id}. No specific action taken as DB pool is managed globally.")
        pass


# Example usage (for testing, not part of the class itself)
async def _test_db_session_internal():
    # This requires db_manager to be set up and a running DB.
    # Also assumes db_manager functions (get_session, add_session) are updated
    # for the new session table structure.
    
    # --- This test section needs db_manager.py to be updated FIRST ---
    # --- to reflect the new session table structure. ---
    # --- It will fail if db_manager still expects a single session_string ---
    
    logger.info("Testing DbSession (requires updated db_manager and running DB with new schema)")
    account_id_to_test = 9999 # Use a distinct ID for testing
    
    # Setup: Ensure db_pool is initialized (normally done in __init__.py)
    try:
        # In a real scenario, db_manager.py would use env vars or config for these.
        # For testing, ensure your local DB is accessible with these or defaults in db_manager.
        await db_manager.get_db_pool() 
        await db_manager.initialize_database() # Ensure tables exist with new schema
        logger.info("DB pool and tables initialized for test.")
    except Exception as e:
        logger.error(f"DB connection/initialization failed: {e}", exc_info=True)
        return

    session = DbSession(account_id=account_id_to_test)

    # 1. Clean up any old test session first (optional, good for rerunning tests)
    logger.info(f"Attempting to delete any pre-existing session for account {account_id_to_test}...")
    await session.delete() # This uses db_manager.delete_session

    # 2. Try to load (should be empty as we just deleted or it's the first time)
    logger.info(f"Attempting to load session for account {account_id_to_test} (should be empty)...")
    await session.load()
    logger.info(f"Initial load: dc_id={session._dc_id}, auth_key={'SET' if session._auth_key else 'NONE'}")
    assert session._auth_key is None, "Auth key should be None on initial load after delete"

    # 3. Simulate setting some data (as Telethon would after a new login)
    logger.info("Simulating setting session data...")
    session.set_dc(2, "149.154.167.51", 443) # DC2 IPv4
    
    import os # for os.urandom
    new_key_data = os.urandom(256)
    new_auth_key = AuthKey(data=new_key_data)
    session.set_auth_key(new_auth_key)
    session.takeout_id = 1234567

    # Mock an UpdateState object (normally comes from Telethon)
    class MockUpdateState: # Simple class to mimic Telethon's state object
        def __init__(self, pts, qts, date, seq, dc_id=None): # dc_id for completeness, not used by set_update_state
            self.pts = pts
            self.qts = qts
            self.date = date # datetime object
            self.seq = seq
            # self.dc_id = dc_id 

    current_time_dt = datetime.now(timezone.utc)
    # Ensure date is timezone-aware for consistent timestamp conversion
    mock_state = MockUpdateState(pts=1001, qts=2002, date=current_time_dt, seq=3003)
    session.set_update_state(mock_state) # This will convert date to timestamp

    # 4. Save the session
    logger.info("Attempting to save session...")
    await session.save() # This uses db_manager.add_session
    logger.info("Save called.")

    # 5. Load again into a new session object to verify
    logger.info("Attempting to load session again into a new instance to verify save...")
    session_verify = DbSession(account_id=account_id_to_test)
    await session_verify.load()
    
    logger.info(f"Verified load: dc_id={session_verify._dc_id}, server={session_verify._server_address}, port={session_verify._port}")
    assert session_verify._dc_id == 2
    assert session_verify._server_address == "149.154.167.51"
    assert session_verify._port == 443
    
    logger.info(f"Verified auth_key is {'SET' if session_verify._auth_key else 'NONE'}")
    assert session_verify._auth_key is not None
    if session_verify._auth_key:
        assert session_verify._auth_key.key == new_key_data, "AuthKey data mismatch"
    
    logger.info(f"Verified takeout_id: {session_verify.takeout_id}")
    assert session_verify.takeout_id == 1234567
    
    logger.info(f"Verified state: pts={session_verify._pts}, qts={session_verify._qts}, date_ts={session_verify._date}, seq={session_verify._seq}")
    expected_timestamp = int(current_time_dt.replace(tzinfo=timezone.utc).timestamp())
    assert session_verify._pts == 1001
    assert session_verify._qts == 2002
    assert session_verify._date == expected_timestamp, f"Timestamp mismatch: got {session_verify._date}, expected {expected_timestamp}"
    assert session_verify._seq == 3003

    # 6. Test get_update_state
    retrieved_state_tuple = session_verify.get_update_state()
    logger.info(f"Retrieved state tuple: {retrieved_state_tuple}")
    assert retrieved_state_tuple is not None
    assert retrieved_state_tuple == (2, 1001, 2002, expected_timestamp, 3003)

    # 7. Delete session
    logger.info("Attempting to delete session...")
    await session_verify.delete()
    logger.info("Delete called.")
    
    session_after_delete = DbSession(account_id=account_id_to_test)
    await session_after_delete.load()
    logger.info(f"After delete, loaded auth_key is {'SET' if session_after_delete._auth_key else 'NONE'} (should be NONE)")
    assert session_after_delete._auth_key is None, "Auth key should be None after delete"
    assert session_after_delete._pts is None, "PTS should be None after delete"

    logger.info("DbSession test completed successfully.")
    await db_manager.close_db_pool()


if __name__ == "__main__":
    # To run this test:
    # 1. Ensure userbot.src.db_manager.py is updated with the new 'sessions' table schema
    #    and corresponding add_session/get_session logic.
    # 2. Ensure you have a PostgreSQL server running and accessible.
    #    Set DB_HOST, DB_PORT, DB_USER, DB_PASS, DB_NAME environment variables if not using defaults
    #    that db_manager.py would connect to.
    # 3. Uncomment the line below:
    # asyncio.run(_test_db_session_internal())
    pass
