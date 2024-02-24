import argparse
import asyncio
import random
import string
import sys
import locale
import codecs

import socks
from faker import Faker
from telethon import TelegramClient
from telethon.tl.functions.channels import JoinChannelRequest
from telethon.extensions import html

from userbot.src.config import *
from userbot.src.preinstall import preinstall


if sys.getdefaultencoding() != 'utf-8':
    locale.setlocale(locale.LC_ALL, 'en_US.utf8')
    codecs.register_error("strict", codecs.ignore_errors)

# Generate FAKE device
FAKE = Faker()
sys_version = "".join(random.choice(string.ascii_uppercase) for _ in range(4))
device_model = random.choice(
    [
        FAKE.android_platform_token(),
        FAKE.ios_platform_token(),
        FAKE.linux_platform_token(),
        FAKE.windows_platform_token(),
    ]
)

# Parse arguments
PARSER = argparse.ArgumentParser(description="Параметры запуска")
PARSER.add_argument("-s", type=str, default="account", help="Путь к сессии")
PARSER.add_argument(
    "-p",
    nargs=5,
    type=str,
    default=None,
    help="Прокси (Proxy Type, IP, Port, username, password)",
)

ARGS = PARSER.parse_args()

# Help information for .help command
help_info = {
    "chat": """<b>❓ ᴋ᧐ʍᴀнды:</b>
            

<b>➖ 𝐂𝐡𝐚𝐭</b>""",
    "fun": """<b>➖ 𝐅𝐮𝐧</b>""",
    "tools": """<b>➖ 𝐓𝐨𝐨𝐥𝐬</b>
<code>.about</code> -> <i>о юзᴇᴩбоᴛᴇ</i>
<code>.addmod</code> -> <i>добᴀʙиᴛь ʍодуᴧь (ᴩᴇᴨᴧᴀᴇʍ нᴀ ɸᴀйᴧ)</i>
<code>.delmod</code> -> <i>удᴀᴧиᴛь ʍодуᴧь</i>""",
}

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


# Check if API_ID and API_HASH are set
if API_ID is None:
    API_ID, API_HASH = preinstall()

# Initialize client
if ARGS.p is not None:
    PROXY_TYPE = None
    if ARGS.p[0].lower() == "http":
        PROXY_TYPE = socks.HTTP
    elif ARGS.p[0].lower() == "socks4":
        PROXY_TYPE = socks.SOCKS4
    elif ARGS.p[0].lower() == "socks5":
        PROXY_TYPE = socks.SOCKS5

    CLIENT = TelegramClient(
        ARGS.s,
        API_ID,
        API_HASH,
        proxy=(
            PROXY_TYPE,
            ARGS.p[1],
            int(ARGS.p[2]),
            True,
            ARGS.p[3] if ARGS.p[3] != "0" else None,
            ARGS.p[4] if ARGS.p[4] != "0" else None,
        ),
        device_model=device_model,
        system_version=f"4.16.30-vxDEBOT{sys_version}",
    )
else:
    CLIENT = TelegramClient(
        ARGS.s,
        API_ID,
        API_HASH,
        device_model=device_model,
        system_version=f"4.16.30-vxDEBOT{sys_version}",
    )


async def start_client():
    """
    Asynchronously starts the client.

    This function starts the client by calling the `start` method of the `client` instance. It then retrieves the entity for the specified channel URL using the `get_entity` method and assigns it to the `entity` variable. Finally, it sends a `JoinChannelRequest` to the client using the retrieved entity.

    Parameters:
        None

    Returns:
        None
    """
    await CLIENT.start()
    entity = await CLIENT.get_entity("https://t.me/DeBot_userbot")
    await CLIENT(JoinChannelRequest(entity))

client = CLIENT

# Run start_client() using asyncio to prevent thread blocking
LOOP = asyncio.get_event_loop()
LOOP.run_until_complete(start_client())
