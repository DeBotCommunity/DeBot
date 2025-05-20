from telethon import TelegramClient
from telethon.extensions import html

class TelegramClient(TelegramClient):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._parse_mode = html

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

        Returns:
            None: RuntimeError.
        """
        raise RuntimeError(
            "Save string session try detected and stopped. Check external libraries."
        )

    async def session(self):
        """
        Session grab guard.

        Returns:
            None: RuntimeError.
        """
        raise RuntimeError(
            "Session contact detected and stopped. Check external libraries."
        )

    async def __call__(self, *args, **kwargs):
        """
        Send commands to main class.

        Parameters:
            *args: Variable length argument list.
            **kwargs: Arbitrary keyword arguments.

        Returns:
            The result of calling the function with the given arguments and keyword arguments.
        """
        return await super().__call__(*args, **kwargs)
