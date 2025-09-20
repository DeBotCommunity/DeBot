# Создание модулей

Каждый модуль в DeBot — это самостоятельный Python-файл, содержащий логику, обработчики событий и специальный блок метаданных.

## Структура модуля

Рекомендуемая структура файла для вашего модуля (`my_module.py`):

```python
# 1. Импорты
from telethon import events
from userbot.src.module_info import ModuleInfo

# 2. Метаданные
__requires__ = ["requests", "pillow"]  # Зависимости
__trusted__ = False  # Требуется ли полный доступ к клиенту
__config__ = {
    "api_key": {
        "default": None, 
        "description": "API ключ для сервиса X"
    },
    "max_items": {
        "default": 10,
        "description": "Максимальное количество элементов для вывода"
    }
}
info = ModuleInfo(
    name="My Module",
    category="tools",
    patterns=[".mycmd"],
    descriptions=["Описание команды .mycmd, включающее упоминание 'api_key' и 'max_items'."]
)

# 3. Логика модуля (обработчики и функции)
async def my_command_handler(event: events.NewMessage.Event):
    # Получение конфига
    config = await event.client.get_module_config("my_module")
    api_key = config.get("api_key")

    # Получение переведенной строки
    response_text = await event.client.get_string("response_message", module_name="my_module")
    
    await event.edit(f"{response_text}: {api_key}")

# 4. Обязательная функция регистрации
def register(client):
    """Регистрирует все обработчики этого модуля."""
    client.add_event_handler(my_command_handler, events.NewMessage(outgoing=True, pattern=r"^\.mycmd$"))
```

## Метаданные

-   `__requires__` (опционально): Список строковых имен Python-пакетов, которые необходимы для работы модуля. DeBot автоматически попытается установить их через `pip` при добавлении модуля.
-   `__trusted__` (опционально): `True` или `False`. Если `True`, модуль считается потенциально опасным и требует явного одобрения от пользователя командой `.trustmod`. Только доверенные модули получают доступ к реальному объекту `TelegramClient`.
-   `__config__` (опционально): Словарь, описывающий настраиваемые параметры модуля. Для каждого ключа можно указать `default` (значение по умолчанию) и `description` (описание).
-   `info` (обязательно): Экземпляр класса `ModuleInfo`, который используется для генерации справки в команде `.help`.

## Функция `register(client)`

Это **обязательная** точка входа для каждого модуля. При загрузке DeBot вызывает эту функцию и передает в нее объект клиента. Внутри этой функции вы должны зарегистрировать все ваши обработчики событий (`.add_event_handler`).

В зависимости от статуса доверия модуля, в `client` будет передан либо **реальный `TelegramClient`** (если модуль доверенный), либо **безопасная обертка `ModuleClient`** (если нет).

## Локализация

Ваши модули могут и должны поддерживать несколько языков.

1.  Создайте папку `locales` внутри папки вашего модуля (например, `userbot/modules/my_module/locales/`).
2.  Внутри создайте JSON-файлы для каждого языка (например, `ru.json`, `en.json`).
    ```json
    // ru.json
    {
        "response_message": "Ваш API ключ"
    }
    ```
3.  В коде модуля получайте строки через `client`, который автоматически определит язык текущего аккаунта:
    ```python
    text = await event.client.get_string("response_message", module_name="my_module")
    ```

Бот будет искать перевод в следующей последовательности:
1.  Перевод модуля на языке аккаунта.
2.  Перевод модуля на русском/английском (fallback).
3.  Системный перевод на языке аккаунта.
4.  Системный перевод на русском/английском (fallback).
