import os
import time
import importlib
import subprocess
import sys

from colorama import Fore
import telethon
from telethon import events
from art import text2art

from userbot.src.config import *
from userbot import *
from userbot.modules import ALL_MODULES


def convert_to_fancy_font(text):
    converted_text = [alphabet.get(char, char) for char in text.lower()]
    return ''.join(converted_text)


def auto_import_modules():
    all_modules = len(ALL_MODULES)
    print(f"-> [modules] - Всего модулей: {all_modules}")
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
                print(f"-> [modules] - Импортирован модуль: {module_name}")
                imported_modules += 1
            except ImportError as e:
                print(f"-> [modules] - Не удалось импортировать модуль: {module_path}, причина: {e}")
            except Exception as e:
                print(f"-> [modules] - Произошла ошибка при импорте модуля {module_path}: {str(e)}")
    print(f"-> [modules] - Импортировано модулей: {imported_modules}")


@client.on(events.NewMessage(pattern=".addmod"))
async def addmod(event):
    await event.delete()
    if not event.is_reply:
        return
    reply_message = await event.get_reply_message()

    if reply_message.media and reply_message.media.document:
        document = reply_message.media.document
        if document.mime_type == 'text/x-python':
            file_name = document.attributes[0].file_name
            module_path = f"{module_folder}.{file_name.split('.')[0]}"
            download_path = module_path.replace(".", "\\")

            await client.download_media(reply_message, file=f'{os.getcwd()}\\{download_path}.py')

            if module_path in sys.modules:
                print(f"-> [.addmod] - Модуль {module_path} уже импортирован.")
            else:
                missing_libraries = []

                try:
                    with open(f'{os.getcwd()}\\{download_path}.py', 'r', encoding='utf-8') as file:
                        for line in file:
                            if line.strip().startswith('import ') or line.startswith('from '):
                                parts = line.split(' ')
                                if len(parts) > 1:
                                    module_name = parts[1].split('.')[0]
                                    if module_name not in sys.modules:
                                        missing_libraries.append(module_name)
                except Exception as e:
                    print(f"-> [.addmod] - Ошибка при чтении файла: {str(e)}")

                if missing_libraries:
                    for lib_name in missing_libraries:
                        subprocess.run(f"pip install {lib_name}", stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)

                try:
                    imported_module = importlib.import_module(module_path)

                    if hasattr(imported_module, 'info'):
                        info_value = imported_module.info
                        if info_value['category'] is not None:
                            for i in range(len(info_value['pattern'].split('|'))):
                                help_info[info_value['category']] += f"\n<code>{info_value['pattern'].split('|')[i]}</code> -> <i>{convert_to_fancy_font(info_value['description'].split('|')[i])}</i>"
                            print(f"-> [.addmod] - Добавлен модуль: {file_name.split('.')[0]}")
                except ImportError as e:
                    print(f"-> [.addmod] - Не удалось импортировать модуль: {module_path}, причина: {e}")
                    os.remove(f'{os.getcwd()}\\{download_path}.py')
                except Exception as e:
                    print(f"-> [.addmod] - Произошла ошибка при импорте модуля {module_path}: {str(e)}")


@client.on(events.NewMessage(pattern='.delmod (.+)'))
async def delmod(event):
    module_name = event.pattern_match.group(1)
    module_path = f"{module_folder}.{module_name}"
    delete_path = module_path.replace(".", "\\")
    path = f"{os.getcwd()}\\{delete_path}.py"

    if os.path.isfile(path):
        try:
            os.remove(path)
            await event.edit(f"✅ <b>Модуль</b> <code>{module_name}</code> <b>успешно удален</b>", parse_mode="HTML")
            print(f"-> [.delmod] - Модуль {module_name} успешно удален")
        except Exception as e:
            await event.edit(f"❌ <b>Произошла ошибка при удалении модуля</b> <code>{module_name}</code>: <code>{str(e)}</code>", parse_mode="HTML")
            print(f"-> [.delmod] - Произошла ошибка при удалении модуля {module_name}: {str(e)}")
    else:
        await event.edit(f"❌ <b>Модуль</b> <code>{module_name}</code> <b>не найден</b>", parse_mode="HTML")
        print(f"-> [.delmod] - Модуль {module_name} не найден")


@client.on(events.NewMessage(outgoing=True, pattern=".help"))
async def help_commands(event):
    print("-> [.help]")
    await client.edit_message(
        event.message,
        help_info['chat']+ '\n' + help_info['fun'] + '\n' + help_info['tools'],
        parse_mode="HTML",
    )


@client.on(events.NewMessage(outgoing=True, pattern=(".about")))
async def awake(event):
    print("-> [.about]")
    await client.edit_message(
        event.message,
        f"""<b>😈 𝚄𝚜𝚎𝚛𝚋𝚘𝚝 𝚋𝚢: <a href="t.me/whynothacked">𝕯𝖊𝕮𝖔𝖉𝖊𝖉</a></b>

<b>💻 𝚃𝚎𝚕𝚎𝚝𝚑𝚘𝚗:</b> <code>{telethon.__version__}</code>""",
        parse_mode="HTML",
    )


if __name__ == "__main__":
    os.system("cls") if os.name == "nt" else os.system("clear")
    print(
        Fore.CYAN
        + text2art('DeBot', font='random', chr_ignore=True)
    ), time.sleep(1)

    print(
        Fore.YELLOW
        + """
                            coded by @whynothacked"""
    ), time.sleep(2)

    (
        print(
            f"""{Fore.RED}            • Пропиши .help в любом чате для получения команд бота"""
        ),
        time.sleep(1),
    )

    print(f"""{Fore.GREEN}                           ↓ Снизу будут логи""")

    auto_import_modules()

    loop.run_forever()
