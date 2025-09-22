import logging
from typing import Set, Any
from telethon import TelegramClient as TelethonTelegramClient

logger: logging.Logger = logging.getLogger(__name__)

class ModuleClient:
    """
    A secure wrapper around the real Telethon client for untrusted modules.

    This class acts as a proxy to the actual TelegramClient instance,
    intercepting calls to potentially dangerous methods and attributes
    to prevent session hijacking or unauthorized actions.
    """

    _FORBIDDEN_ATTRS: Set[str] = {
        'session', 'log_out', '__call__', 'disconnected',
        'is_connected', 'connect', 'disconnect', 'save', 'get_all_clients'
    }

    def __init__(self, real_client: TelethonTelegramClient):
        """
        Initializes the proxy client.

        Args:
            real_client (TelethonTelegramClient): The actual, real instance of the
                Telethon client that this class will wrap.

        Raises:
            TypeError: If the provided `real_client` is not a valid Telethon client instance.
        """
        if not isinstance(real_client, TelethonTelegramClient):
            raise TypeError("ModuleClient must be initialized with a valid Telethon client instance.")
        # Use a non-standard name to avoid clashes with proxied attributes.
        object.__setattr__(self, '_real_client_instance', real_client)

    def __getattr__(self, name: str) -> Any:
        """
        Proxies attribute access to the real client.

        Args:
            name (str): The name of the attribute being accessed.

        Returns:
            Any: The attribute from the real client.

        Raises:
            PermissionError: If access to a forbidden attribute is attempted.
        """
        if name in self._FORBIDDEN_ATTRS:
            logger.warning(f"Untrusted module attempted to access forbidden client attribute: '{name}'")
            raise PermissionError(f"Access to the '{name}' attribute is forbidden for untrusted modules.")
        
        return getattr(object.__getattribute__(self, '_real_client_instance'), name)

    def __setattr__(self, name: str, value: Any) -> None:
        """
        Prevents setting attributes on the proxy.

        Args:
            name (str): The name of the attribute.
            value (Any): The value to set.

        Raises:
            PermissionError: Always raised to indicate that the proxy is read-only.
        """
        logger.warning(f"Untrusted module attempted to set client attribute: '{name}'")
        raise PermissionError("Setting attributes on the client is forbidden for untrusted modules.")

    def __delattr__(self, name: str) -> None:
        """
        Prevents deleting attributes on the proxy.

        Args:
            name (str): The name of the attribute to delete.

        Raises:
            PermissionError: Always raised to indicate that attributes cannot be deleted.
        """
        logger.warning(f"Untrusted module attempted to delete client attribute: '{name}'")
        raise PermissionError("Deleting attributes on the client is forbidden for untrusted modules.")
