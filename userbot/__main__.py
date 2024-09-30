from userbot import *
from userbot.modules import ALL_MODULES
from userbot.src.config import *

import importlib
import importlib.util
import os
import sys
import time
from pathlib import Path
from tqdm import tqdm

import telethon
from art import text2art
from telethon import events


def convert_to_fancy_font(text):
    """
    Convert the given text to a fancy font.

    Args:
        text (str): The text to convert.

    Returns:
        str: The converted text.
    """
    converted_text = [ALPHABET.get(char, char) for char in text.lower()]
    return "".join(converted_text)


def auto_import_modules():
    """
    Auto import modules and display information about imported modules.
    """
    all_modules = len(ALL_MODULES)
    logger.info(f"-> [modules] - Всего модулей: {all_modules}")
    imported_modules = 0
    for module_name in tqdm(ALL_MODULES, desc="Импорт модулей", total=all_modules):
        module_path = f"{MODULE_FOLDER}.{module_name}"
        if not module_path.startswith("."):
            try:
                imported_module = importlib.import_module(module_path)
                if hasattr(imported_module, "info"):
                    info_value = imported_module.info
                    if info_value["category"] != None or info_value["category"] != "":
                        for i in range(len(info_value["pattern"].split("|"))):
                            help_info[
                                info_value["category"]
                            ] += f"\n<code>{info_value['pattern'].split('|')[i]}</code> -> <i>{convert_to_fancy_font(info_value['description'].split('|')[i])}</i>"
                logger.info(
                    f"-> [modules] - Импортирован модуль: {module_name}"
                )
                imported_modules += 1
            except ImportError as e:
                logger.error(
                    f"-> [modules] - Не удалось импортировать модуль: {module_path}, причина: {e}"
                )
            except Exception as e:
                logger.error(
                    f"-> [modules] - Произошла ошибка при импорте модуля {module_path}: {str(e)}"
                )
    logger.info(f"-> [modules] - Импортировано модулей: {imported_modules}")


async def load_module_sortner(event, file_name, download_path, module_path):
    """
    Asynchronously loads a module and sorts its information.

    Args:
        event (Event): The event triggering the function.
        file_name (str): The name of the file containing the module.
        download_path (str): The path where the module is downloaded.
        module_path (str): The path of the module.

    Returns:
        None
    """
    module_name = file_name.split(".")[0]
    path = Path(f"userbot/modules/{file_name}")

    if not path.exists():
        event.edit(f"❌ Файл модуля {file_name} не найден.")
        return

    name = f"{MODULE_FOLDER}.{module_name}"
    spec = importlib.util.spec_from_file_location(name, path)

    if spec is None:
        event.edit(f"❌ Не удалось загрузить спецификацию для {name}.")
        return

    try:
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        if hasattr(mod, "info"):
            info_value = mod.info
            if info_value["category"] is not None:
                patterns = info_value["pattern"].split("|")
                descriptions = info_value["description"].split("|")
                for pattern, description in zip(patterns, descriptions):
                    help_info[
                        info_value["category"]
                    ] += f"\n<code>{pattern}</code> -> <i>{convert_to_fancy_font(description)}</i>"
        logger.info(f"-> [.addmod] - Добавлен модуль: {module_name}")
        await event.edit(
            f"✅ <b>Модуль</b> <code>{module_name}</code> <b>успешно добавлен</b>",
            parse_mode="HTML",
        )

    except ImportError as e:
        event.edit(f"❌ Ошибка импорта модуля {module_name}: {e}")
    except Exception as e:
        event.edit(f"❌ Произошла ошибка при обработке модуля {module_name}: {e}")


@CLIENT.on(events.NewMessage(outgoing=True, pattern=r"^\.addmod$"))
async def addmod(event):
    """
    Add a module to the bot's runtime environment.

    Parameters:
        event (Event): The event that triggered the function.

    Returns:
        None
    """
    if not event.is_reply:
        return
    reply_message = await event.get_reply_message()

    if reply_message.media and reply_message.media.document:
        document = reply_message.media.document
        if document.mime_type == "text/x-python":
            file_name = document.attributes[0].file_name
            module_name = file_name.split(".")[0]
            module_path = f"{MODULE_FOLDER}.{module_name}"
            download_path = os.path.join(
                os.getcwd(), MODULE_FOLDER.replace(".", os.sep), f"{module_name}.py"
            )

            if module_path in sys.modules:
                await event.edit(
                    f"❌ Модуль <code>{module_name}</code> уже импортирован.",
                    parse_mode="HTML",
                )
                logger.error(
                    f"→ [.addmod] - Модуль {module_name} уже импортирован.",
                )
            else:
                await CLIENT.download_media(reply_message, file=download_path)
                await load_module_sortner(event, file_name, download_path, module_path)


@CLIENT.on(events.NewMessage(pattern=r"^\.delmod (\w+)$"))
async def delmod(event):
    """
    Deletes a module from the userbot.

    Parameters:
    - event: The event triggering the function.

    Returns:
    - None

    Raises:
    - None
    """
    module_name = event.pattern_match.group(1)
    module_path = f"userbot.modules.{module_name}"
    delete_path = module_path.replace(".", "/")
    path = f"{os.getcwd()}/{delete_path}.py"

    if os.path.isfile(path):
        try:
            os.remove(path)
            await event.edit(
                f"✅ <b>Модуль</b> <code>{module_name}</code> <b>успешно удален</b>",
                parse_mode="HTML",
            )
            logger.info(
                f"-> [.delmod] - Модуль {module_name} успешно удален",
            )

            for i in CLIENT.list_event_handlers():
                if isinstance(
                    i,
                    (
                        events.NewMessage,
                        events.MessageDeleted,
                        events.MessageEdited,
                        events.MessageRead,
                        events.MessagePinned,
                        events.MessageUnpinned,
                        events.UserUpdate,
                    ),
                ) and module_path in str(i.callback):
                    CLIENT.remove_event_handler(i)

            for name in list(sys.modules):
                if name.startswith(module_path):
                    del sys.modules[name]

        except Exception as e:
            await event.edit(
                f"❌ <b>Произошла ошибка при удалении модуля</b> <code>{module_name}</code>: <code>{str(e)}</code>",
                parse_mode="HTML",
            )
            logger.error(
                f"-> [.delmod] - Произошла ошибка при удалении модуля {module_name}: {str(e)}",
            )
    else:
        await event.edit(
            f"❌ <b>Модуль</b> <code>{module_name}</code> <b>не найден</b>",
            parse_mode="HTML",
        )
        logger.error(f"-> [.delmod] - Модуль {module_name} не найден")


@CLIENT.on(events.NewMessage(outgoing=True, pattern=r"^\.help$"))
async def help_commands(event):
    """
    Handles the event of a new outgoing message with the pattern ".help".

    Parameters:
        event (events.NewMessage): The event object representing the new message.

    Returns:
        None
    """
    logger.info("-> [.help]")
    await CLIENT.edit_message(
        event.message,
        help_info["chat"] + "\n" + help_info["fun"] + "\n" + help_info["tools"],
        parse_mode="HTML",
    )


@CLIENT.on(events.NewMessage(outgoing=True, pattern=r"^\.about$"))
async def awake(event):
    """
    A function to handle the event of a new outgoing message with the pattern ".about".

    Parameters:
        event (events.NewMessage): The event object representing the new message.

    Returns:
        None
    """
    logger.info("-> [.about]")
    await CLIENT.edit_message(
        event.message,
        f"""<b>😈 𝚄𝚜𝚎𝚛𝚋𝚘𝚝 𝚋𝚢: <a href="t.me/whynothacked">𝕯𝖊𝕮𝖔𝖉𝖊𝖉</a></b>

<b>💻 𝚃𝚎𝚕𝚎𝚝𝚑𝚘𝚗:</b> <code>{telethon.__version__}</code>""",
        parse_mode="HTML",
    )


if __name__ == "__main__":
    # Clear the console
    os.system("cls") if os.name == "nt" else os.system("clear")

    # Print the ASCII art
    ASCII_ART = text2art("DeBot", font="random", chr_ignore=True)
    print(f"\033[33m{ASCII_ART}\033[0m")

    time.sleep(1)

    print(
        """\033[31m
                            coded by @whynothacked\033[0m"""
    )

    time.sleep(2)

    (
        print(
            """\033[32m            • Пропиши .help в любом чате для получения команд бота\033[0m"""
        ),
        time.sleep(1),
    )

    print("""\033[34m                           ↓ Снизу будут логи\033[0m""")

    # Import all modules
    auto_import_modules()

    # Start the userbot
    LOOP.run_forever()
