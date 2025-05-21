from telethon import TelegramClient # Base client
from telethon.extensions import html
import json # For potential future use, good to have if dealing with complex data types
import logging
from typing import Optional, Any

import userbot.src.db_manager as db_manager
# Assuming DbSession might be used for type hinting or direct access later, though not strictly in this part
# from userbot.src.db_session import DbSession 

logger = logging.getLogger(__name__)

class TelegramClient(TelegramClient): # Inherits from the imported telethon.TelegramClient
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._parse_mode = html # Existing custom attribute from original file

    @property
    def current_account_id(self) -> Optional[int]:
        """
        Retrieves the account_id from the current session.
        The session object is expected to have an 'account_id' attribute if it's a DbSession.
        """
        # Ensure self.session exists and then check for account_id
        # This relies on the session being a DbSession instance, which should set account_id
        if hasattr(self, 'session') and self.session is not None and hasattr(self.session, 'account_id'):
            account_id = getattr(self.session, 'account_id', None)
            if account_id is not None:
                return account_id
        logger.warning("Could not determine current_account_id from session. Ensure session is DbSession and account_id is set.")
        return None

    async def save_module_data(self, module_name: str, key: str, value: Any) -> bool:
        account_id = self.current_account_id
        if account_id is None:
            logger.error("save_module_data: Could not get account_id.")
            return False
        if not isinstance(module_name, str) or not module_name.strip():
            logger.error("save_module_data: module_name must be a non-empty string.")
            return False
        # Ensure db_manager and its functions are correctly imported and available
        return await db_manager.save_module_data(account_id, module_name, key, value)

    async def get_module_data(self, module_name: str, key: str) -> Any:
        account_id = self.current_account_id
        if account_id is None:
            logger.error("get_module_data: Could not get account_id.")
            return None
        if not isinstance(module_name, str) or not module_name.strip():
            logger.error("get_module_data: module_name must be a non-empty string.")
            return None
        return await db_manager.get_module_data(account_id, module_name, key)

    async def delete_module_data(self, module_name: str, key: str) -> bool:
        account_id = self.current_account_id
        if account_id is None:
            logger.error("delete_module_data: Could not get account_id.")
            return False
        if not isinstance(module_name, str) or not module_name.strip():
            logger.error("delete_module_data: module_name must be a non-empty string.")
            return False
        return await db_manager.delete_module_data(account_id, module_name, key)

    async def get_all_module_data(self, module_name: str) -> dict:
        account_id = self.current_account_id
        if account_id is None:
            logger.error("get_all_module_data: Could not get account_id.")
            return {} # Return empty dict on error
        if not isinstance(module_name, str) or not module_name.strip():
            logger.error("get_all_module_data: module_name must be a non-empty string.")
            return {}
        return await db_manager.get_all_module_data(account_id, module_name)

    # --- Existing methods from the original class (as per the file content provided) ---
    @property
    def parse_mode(self):
        """
        A property method that returns the parse mode.
        """
        return self._parse_mode

    @parse_mode.setter
    def parse_mode(self, mode):
        """
        Setter for the parse_mode property.

        Args:
            mode: The parse mode to be set.

        Returns:
            None
        """
        pass

    async def save(self):
        """
        Session grab guard.
        """
        # This guard might need adjustment if DbSession is used and has a specific save protocol,
        # but for now, keeping original logic as the prompt implies minimal changes to existing methods.
        # If self.session is a DbSession, it handles its own saving.
        # This explicit .save() might be from external code trying to save a string session.
        if hasattr(self, 'session') and self.session is not None and type(self.session).__name__ == 'DbSession':
             logger.info("Custom 'save' method called with DbSession. DbSession handles its own persistence.")
             return # Explicitly do nothing for DbSession, as it auto-saves or has its own mechanism.

        raise RuntimeError(
            "Save string session try detected and stopped. Check external libraries or ensure DbSession is used."
        )

    async def session(self): # This method name is problematic as it overrides the session property.
        """
        Session grab guard.
        """
        # This method overrides a critical Telethon property `client.session`.
        # It's highly recommended to remove or rename this to avoid breaking Telethon.
        # For this task, I am keeping it as per "Keep the existing methods... as they are",
        # but logging a strong warning.
        logger.critical("The custom `async def session(self)` method in TelegramClient overrides a "
                       "critical Telethon property and will likely break client.session access. "
                       "This method should be removed or renamed.")
        raise RuntimeError(
            "Session contact detected and stopped. Check external libraries."
        )

    async def __call__(self, *args, **kwargs):
        """
        Send commands to main class.
        """
        return await super().__call__(*args, **kwargs)
