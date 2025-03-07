# DeBot | Лучший модульный userbot для Telegram
![Telegram](https://img.shields.io/badge/Telegram-2CA5E0?style=for-the-badge&logo=telegram&logoColor=white)
![Python](https://img.shields.io/badge/python-3670A0?style=for-the-badge&logo=python&logoColor=ffdd54)

![Issues](https://img.shields.io/github/issues/DeBotCommunity/DeBot)
![GitHub License](https://img.shields.io/github/license/DeBotCommunity/DeBot)
![GitHub Repo stars](https://img.shields.io/github/stars/DeBotCommunity/DeBot)

```mermaid
graph TB
    %% External Actors
    User((Telegram User))
    TelegramAPI((Telegram API))

    subgraph "DeBot System"
        subgraph "Core Bot Container (Python)"
            BotClient["Bot Client<br>(Telethon)"]
            ModuleManager["Module Manager<br>(Python)"]
            ConfigManager["Config Manager<br>(python-dotenv)"]
            
            subgraph "Module Components"
                ModuleLoader["Module Loader<br>(Python)"]
                CommandHandler["Command Handler<br>(Python)"]
                SessionManager["Session Manager<br>(Telethon)"]
            end
            
            subgraph "Utility Components"
                FakeDataGen["Fake Data Generator<br>(Faker)"]
                ConsoleUI["Console UI<br>(Rich)"]
                ArtRenderer["ASCII Art Renderer<br>(Art)"]
                SystemMonitor["System Monitor<br>(WMI)"]
            end
        end

        subgraph "Network Layer"
            ProxyHandler["Proxy Handler<br>(PySocks/python-socks)"]
        end
    end

    %% Relationships
    User -->|"Interacts with"| TelegramAPI
    TelegramAPI -->|"Communicates via"| ProxyHandler
    ProxyHandler -->|"Routes traffic to"| BotClient
    
    BotClient -->|"Loads"| ModuleManager
    ModuleManager -->|"Uses"| ModuleLoader
    ModuleManager -->|"Registers"| CommandHandler
    BotClient -->|"Manages"| SessionManager
    
    BotClient -->|"Configures via"| ConfigManager
    
    CommandHandler -->|"Uses"| FakeDataGen
    CommandHandler -->|"Outputs via"| ConsoleUI
    ConsoleUI -->|"Renders"| ArtRenderer
    CommandHandler -->|"Monitors via"| SystemMonitor
```

## Установка:
```sh
git clone https://github.com/DeBotCommunity/DeBot.git
cd DeBot
pip3 instal -r requirements.txt
```

## Запуск

### Описание параметров
- `-s`: Название файла сессии. Тип аргумента: строка. Значение по умолчанию: account
- `-p`: Настройки прокси. Параметр принимает 5 значений: Тип Прокси, IP, Порт, Имя пользователя и Пароль. Тип значения: список строк (nargs=5). Полная поддержка HTTP/S, SOCKS4, SOCKS5

## Примеры запуска: 
1. **Запуск с параметром пути к сессии:**
   ```sh
   python3 -m userbot -s "путь_к_сессии"
   ```
2. **Запуск с параметрами прокси:**
   ```sh
   python3 -m userbot -p "Тип_Прокси" "IP" "Порт" "Имя_пользователя" "Пароль"
   ```
3. **Запуск с обоими параметрами:**
   ```sh
   python3 -m userbot -s "путь_к_сессии" -p "Тип_Прокси" "IP" "Порт" "Имя_пользователя" "Пароль"
   ```

## Стоковые команды:
- `.addmod` - добавление модуля. Отправляется реплаем на файл с модулем, зависимости модуля обнаруживаются и устанавливаются автоматически.
- `.delmod <имя модуля>` - удаление модуля.
- `.help` - справка.
- `.about` - о юзерботе.

## Telegram Канал: [DeBot | Main](https://t.me/DeBot_userbot)
Предложить модуль в канал или задонатить: [@whynothacked](https://t.me/whynothacked)
