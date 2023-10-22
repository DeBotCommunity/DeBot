import asyncio
from telethon import TelegramClient
from telethon.tl.functions.channels import GetParticipantsRequest, JoinChannelRequest
from telethon.tl.types import ChannelParticipantsSearch
from userbot.src.config import *
from userbot.src.preinstall import preinstall

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

client = TelegramClient("account", api_id, api_hash, system_version="4.16.30-vxDECODED", auto_reconnect=True)


async def start_client():
    await client.start()


loop = asyncio.get_event_loop()
loop.run_until_complete(start_client())
