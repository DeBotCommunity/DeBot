import argparse
import asyncio
import random
import string

import socks
from faker import Faker
from telethon import TelegramClient
from telethon.tl.functions.channels import JoinChannelRequest

from userbot.src.config import *
from userbot.src.preinstall import preinstall

fake = Faker()
rand_sys_version = ''.join(random.choice(string.ascii_uppercase) for _ in range(4))
device_model = random.choice([fake.android_platform_token(), fake.ios_platform_token(), fake.linux_platform_token(), fake.windows_platform_token()])

parser = argparse.ArgumentParser(description="Параметры запуска")
parser.add_argument("-s", type=str, default="account", help="Путь к сессии")
parser.add_argument('-p', nargs=5, type=str, default=None, help='Прокси (Proxy Type, IP, Port, username, password)')

args = parser.parse_args()

help_info = {
'chat': """<b>❓ ᴋ᧐ʍᴀнды:</b>
            

<b>➖ 𝐂𝐡𝐚𝐭</b>""",

'fun': """<b>➖ 𝐅𝐮𝐧</b>""",

'tools': """<b>➖ 𝐓𝐨𝐨𝐥𝐬</b>
<code>.about</code> -> <i>о юзᴇᴩбоᴛᴇ</i>
<code>.addmod</code> -> <i>добᴀʙиᴛь ʍодуᴧь (ᴩᴇᴨᴧᴀᴇʍ нᴀ ɸᴀйᴧ)</i>
<code>.delmod</code> -> <i>удᴀᴧиᴛь ʍодуᴧь</i>"""
}

if api_id is None:
    api_id, api_hash = preinstall()

if args.p is not None:
    proxy_type = None
    if args.p[0].lower() == 'http':
        proxy_type = socks.HTTP
    elif args.p[0].lower() == 'socks4':
        proxy_type = socks.SOCKS4
    elif args.p[0].lower() == 'socks5':
        proxy_type = socks.SOCKS5

    client = TelegramClient(args.s, api_id, api_hash, proxy=(proxy_type, args.p[1], int(args.p[2]), True, args.p[3] if args.p[3] != '0' else None, args.p[4] if args.p[4] != '0' else None), device_model=device_model, system_version=f"4.16.30-vxDEBOT{rand_sys_version}")
else:
    client = TelegramClient(args.s, api_id, api_hash, device_model=device_model, system_version=f"4.16.30-vxDEBOT{rand_sys_version}")


async def start_client():
    await client.start()
    entity = await client.get_entity('https://t.me/DeBot_userbot')
    await client(JoinChannelRequest(entity))


loop = asyncio.get_event_loop()
loop.run_until_complete(start_client())
