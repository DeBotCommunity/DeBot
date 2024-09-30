import argparse
import asyncio
import random
import string
import sys
import locale
import codecs

import socks
from faker import Faker
from telethon.tl.functions.channels import JoinChannelRequest
from ruamel.yaml import YAML
from loguru import logger

from userbot.src.config import *
from userbot.src.setup import setup
from userbot.src.custom_client import TelegramClient
from userbot.src.db import AIOPostgresDB


if sys.getdefaultencoding() != "utf-8":
    locale.setlocale(locale.LC_ALL, "en_US.utf8")
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


# Check if API_ID and API_HASH are set
if API_ID is None:
    API_ID, API_HASH = setup()

os.system("docker compose up -d")

with open("Docker-compose.yaml") as f:
    yaml = YAML(typ="safe")
    config = yaml.load(f)

postgres_config = config["services"]["database"]

postgres_user = postgres_config["environment"]["POSTGRES_USER"]
postgres_password = postgres_config["environment"]["POSTGRES_PASSWORD"]
postgres_db = postgres_config["environment"]["POSTGRES_DB"]

CURSOR = AIOPostgresDB(
    database=postgres_db,
    user=postgres_user,
    password=postgres_password,
    create_table=TABLE,
)

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


# Функция-обёртка для вызова асинхронного обработчика
def loguru_async_handler(message):
    LOOP = asyncio.get_event_loop()
    LOOP.run_until_complete(AIOPostgresDB()(message))


# Добавление обработчика к Loguru
logger.add(loguru_async_handler, level="INFO")

# Run start_client() using asyncio to prevent thread blocking
LOOP = asyncio.get_event_loop()
LOOP.run_until_complete(start_client())
