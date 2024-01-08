import argparse
import asyncio
import random
import string
import inspect

import socks
from faker import Faker
from telethon import TelegramClient
from telethon.tl.functions.channels import JoinChannelRequest

from userbot.src.config import *
from userbot.src.preinstall import preinstall

# Generate fake device
fake = Faker()
rand_sys_version = "".join(random.choice(string.ascii_uppercase) for _ in range(4))
device_model = random.choice(
    [
        fake.android_platform_token(),
        fake.ios_platform_token(),
        fake.linux_platform_token(),
        fake.windows_platform_token(),
    ]
)

# Parse arguments
parser = argparse.ArgumentParser(description="Параметры запуска")
parser.add_argument("-s", type=str, default="account", help="Путь к сессии")
parser.add_argument(
    "-p",
    nargs=5,
    type=str,
    default=None,
    help="Прокси (Proxy Type, IP, Port, username, password)",
)

args = parser.parse_args()

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
    async def save(self):
        """
        Saves string session if not called from external libraries.

        Returns:
            str: String session or RuntimeError.
        """
        stack = inspect.stack()
        caller_filename = stack[1][1]
        if caller_filename != "__init__.py" and caller_filename != "__main__.py":
            raise RuntimeError(
                "Save string session try detected and stopped. Check external libraries."
            )
        return await self.save()

    def __call__(self, *args, **kwargs):
        """
        Send commands to main class.

        Parameters:
            *args: Variable length argument list.
            **kwargs: Arbitrary keyword arguments.

        Returns:
            The result of calling the function with the given arguments and keyword arguments.
        """
        return super().__call__(*args, **kwargs)


# Check if api_id and api_hash are set
if api_id is None:
    api_id, api_hash = preinstall()

# Initialize client
if args.p is not None:
    proxy_type = None
    if args.p[0].lower() == "http":
        proxy_type = socks.HTTP
    elif args.p[0].lower() == "socks4":
        proxy_type = socks.SOCKS4
    elif args.p[0].lower() == "socks5":
        proxy_type = socks.SOCKS5

    client = TelegramClient(
        args.s,
        api_id,
        api_hash,
        proxy=(
            proxy_type,
            args.p[1],
            int(args.p[2]),
            True,
            args.p[3] if args.p[3] != "0" else None,
            args.p[4] if args.p[4] != "0" else None,
        ),
        device_model=device_model,
        system_version=f"4.16.30-vxDEBOT{rand_sys_version}",
    )
else:
    client = TelegramClient(
        args.s,
        api_id,
        api_hash,
        device_model=device_model,
        system_version=f"4.16.30-vxDEBOT{rand_sys_version}",
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
    await client.start()
    entity = await client.get_entity("https://t.me/DeBot_userbot")
    await client(JoinChannelRequest(entity))


# Run start_client() using asyncio to prevent thread blocking
loop = asyncio.get_event_loop()
loop.run_until_complete(start_client())
