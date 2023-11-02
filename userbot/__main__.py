import importlib
import importlib.util
import os
import fnmatch
import sys
import time
from pathlib import Path

import telethon
from art import text2art
from rich.console import Console
from telethon import events

from userbot import *
from userbot.modules import ALL_MODULES
from userbot.src.config import *


def convert_to_fancy_font(text):
    converted_text = [alphabet.get(char, char) for char in text.lower()]
    return ''.join(converted_text)


def auto_import_modules():
    all_modules = len(ALL_MODULES)
    console.print(f"-> [modules] - Всего модулей: {all_modules}", style="bold green")
    imported_modules = 0
    for module_name in ALL_MODULES:
        module_path = f"{module_folder}.{module_name}"
        if not module_path.startswith('.'):
            try:
                imported_module = importlib.import_module(module_path)
                if hasattr(imported_module, 'info'):
                    info_value = imported_module.info
                    if info_value['category'] != None:
                        for i in range(len(info_value['pattern'].split('|'))):
                            help_info[info_value['category']] += f"\n<code>{info_value['pattern'].split('|')[i]}</code> -> <i>{convert_to_fancy_font(info_value['description'].split('|')[i])}</i>"
                console.print(f"-> [modules] - Импортирован модуль: {module_name}", style="bold green")
                imported_modules += 1
            except ImportError as e:
                console.print(f"-> [modules] - Не удалось импортировать модуль: {module_path}, причина: {e}", style="bold red")
            except Exception as e:
                console.print(f"-> [modules] - Произошла ошибка при импорте модуля {module_path}: {str(e)}", style="bold red")
    console.print(f"-> [modules] - Импортировано модулей: {imported_modules}", style="bold green")


async def load_module_sortner(event, file_name, download_path, module_path):
    path = Path(f"userbot/modules/{file_name}")
    name = f"userbot.modules.{file_name}"
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    
    spec.loader.exec_module(mod)

    try:
        if hasattr(mod, 'info'):
            info_value = mod.info
            if info_value['category'] is not None:
                for i in range(len(info_value['pattern'].split('|'))):
                    help_info[info_value['category']] += f"\n<code>{info_value['pattern'].split('|')[i]}</code> -> <i>{convert_to_fancy_font(info_value['description'].split('|')[i])}</i>"
                console.print(f"-> [.addmod] - Добавлен модуль: {file_name.split('.')[0]}", style="bold green")
                await event.edit(f"✅ <b>Модуль</b> <code>{file_name.split('.')[0]}</code> <b>успешно добавлен</b>", parse_mode="HTML")
    except ImportError as e:
        console.print(f"-> [.addmod] - Не удалось импортировать модуль: {module_path}, причина: {e}", style="bold red")
        os.remove(f'{os.getcwd()}/{download_path}.py')
    except Exception as e:
        console.print(f"-> [.addmod] - Произошла ошибка при импорте модуля {module_path}: {str(e)}", style="bold red")


@client.on(events.NewMessage(outgoing=True, pattern=r'^\.addmod$'))
async def addmod(event):
    if not event.is_reply:
        return
    reply_message = await event.get_reply_message()

    if reply_message.media and reply_message.media.document:
        document = reply_message.media.document
        if document.mime_type == 'text/x-python':
            file_name = document.attributes[0].file_name
            module_path = f"{module_folder}.{file_name.split('.')[0]}"
            download_path = module_path.replace(".", "/")

            await client.download_media(reply_message, file=f'{os.getcwd()}/{download_path}.py')

            if module_path in sys.modules:
                await event.edit(f"❌ Модуль <code>{file_name.split('.')[0]}</code> уже импортирован.", parse_mode="HTML")
                console.print(f"→ [.addmod] - Модуль {file_name.split('.')[0]} уже импортирован.", style="bold red")
            else:
                await load_module_sortner(event, file_name, download_path, module_path)


@client.on(events.NewMessage(pattern=r'^\.delmod (\w+)$'))
async def delmod(event):
    module_name = event.pattern_match.group(1)
    module_path = f"userbot.modules.{module_name}"
    delete_path = module_path.replace(".", "/")
    path = f"{os.getcwd()}/{delete_path}.py"

    if os.path.isfile(path):
        try:
            os.remove(path)
            await event.edit(f"✅ <b>Модуль</b> <code>{module_name}</code> <b>успешно удален</b>", parse_mode="HTML")
            console.print(f"-> [.delmod] - Модуль {module_name} успешно удален", style="bold green")

            for i in client.list_event_handlers():
                if isinstance(i, events.CallbackQuery) and module_name in i._event.instance.__module__:
                    client.remove_event_handler(i)

            if module_name in sys.modules:
                del sys.modules[module_name]

        except Exception as e:
            await event.edit(f"❌ <b>Произошла ошибка при удалении модуля</b> <code>{module_name}</code>: <code>{str(e)}</code>", parse_mode="HTML")
            console.print(f"-> [.delmod] - Произошла ошибка при удалении модуля {module_name}: {str(e)}", style="bold red")
    else:
        await event.edit(f"❌ <b>Модуль</b> <code>{module_name}</code> <b>не найден</b>", parse_mode="HTML")
        console.print(f"-> [.delmod] - Модуль {module_name} не найден", style="bold red")


@client.on(events.NewMessage(outgoing=True, pattern=r'^\.help$'))
async def help_commands(event):
    console.print("-> [.help]")
    await client.edit_message(
        event.message,
        help_info['chat']+ '\n' + help_info['fun'] + '\n' + help_info['tools'],
        parse_mode="HTML",
    )


@client.on(events.NewMessage(outgoing=True, pattern=r'^\.about$'))
async def awake(event):
    console.print("-> [.about]")
    await client.edit_message(
        event.message,
        f"""<b>😈 𝚄𝚜𝚎𝚛𝚋𝚘𝚝 𝚋𝚢: <a href="t.me/whynothacked">𝕯𝖊𝕮𝖔𝖉𝖊𝖉</a></b>

<b>💻 𝚃𝚎𝚕𝚎𝚝𝚑𝚘𝚗:</b> <code>{telethon.__version__}</code>""",
        parse_mode="HTML",
    )


if __name__ == "__main__":
    os.system("cls") if os.name == "nt" else os.system("clear")
    console = Console()

    console.print(
        text2art('DeBot', font='random', chr_ignore=True)
    , style='cyan'), time.sleep(1)

    console.print(
        """
                            coded by @whynothacked"""
    , style='yellow'), time.sleep(2)

    (
        console.print(
            """            • Пропиши .help в любом чате для получения команд бота"""
        , style='red'),
        time.sleep(1),
    )

    console.print("""                           ↓ Снизу будут логи""", style='green')

    auto_import_modules()

    loop.run_forever()
