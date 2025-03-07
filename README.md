# DeBot | Лучший модульный userbot для Telegram
![Telegram](https://img.shields.io/badge/Telegram-2CA5E0?style=for-the-badge&logo=telegram&logoColor=white)
![Python](https://img.shields.io/badge/python-3670A0?style=for-the-badge&logo=python&logoColor=ffdd54)

```mermaid
graph TB
    User((User))
    
    subgraph "DeBot System"
        subgraph "Bot Application"
            TelegramBot["Telegram Bot Client<br>(Telethon)"]
            
            subgraph "Core Components"
                ConfigManager["Configuration Manager<br>(python-dotenv)"]
                ProxyHandler["Proxy Handler<br>(PySocks/python-socks)"]
                FakeDataGen["Fake Data Generator<br>(Faker)"]
                SystemInfo["System Monitor<br>(wmi)"]
                ConsoleUI["Console Interface<br>(rich)"]
                ArtRenderer["ASCII Art Renderer<br>(art)"]
                EncryptionManager["Session Encryption<br>(cryptography)"]
                LanguageManager["Localization Engine<br>(gettext)"]
                ModuleManager["Dynamic Module Loader"]
                SessionImporter["Multi-Session Adapter"]
                AutoUpdater["Auto-Updater System"]
                FontConfigurator["Font Configurator"]
                ShareManager["Settings Sharing"]
            end

            subgraph "Module Ecosystem"
                Module1["Spam Module"]
                Module2["Scraper Module"]
                Module3["AI Assistant"]
            end
        end
        
        subgraph "External Dependencies"
            TelegramAPI["Telegram API<br>(External Service)"]
            ProxyServers["Proxy Servers<br>(External Service)"]
            GitHub["GitHub API<br>(Auto-Update)"]
            ConfigCloud["Settings Cloud<br>(User Sharing)"]
        end
    end

    User -->|"Interacts with"| TelegramBot
    TelegramBot -->|"Authenticates and communicates"| TelegramAPI
    TelegramBot -->|"Uses"| ConfigManager
    TelegramBot -->|"Routes through"| ProxyHandler
    ProxyHandler -->|"Connects to"| ProxyServers
    TelegramBot -->|"Generates data using"| FakeDataGen
    TelegramBot -->|"Monitors system with"| SystemInfo
    TelegramBot -->|"Displays using"| ConsoleUI
    ConsoleUI -->|"Renders"| ArtRenderer
    ConfigManager -->|"Secures with"| EncryptionManager
    TelegramBot -->|"Supports multiple"| SessionImporter
    ModuleManager -->|"Manages"| Module1
    ModuleManager -->|"Manages"| Module2
    ModuleManager -->|"Manages"| Module3
    TelegramBot -->|"Loads modules via"| ModuleManager
    AutoUpdater -->|"Checks updates via"| GitHub
    TelegramBot -->|"Updates through"| AutoUpdater
    ConsoleUI -->|"Customizes with"| FontConfigurator
    LanguageManager -->|"Uses"| ConfigManager
    TelegramBot -->|"Localizes via"| LanguageManager
    ShareManager -->|"Syncs with"| ConfigCloud
    ConfigManager -->|"Shares via"| ShareManager
```

## Стоковые команды:
- `.addmod` - добавление модуля. Отправляется реплаем на файл с модулем, зависимости модуля обнаруживаются и устанавливаются автоматически.
- `.delmod <имя модуля>` - удаление модуля.
- `.help` - справка.
- `.about` - о юзерботе.

## Канал: [DeBot_userbot](https://t.me/DeBot_userbot)
Предложить модуль в канал или задонатить: @whynothacked
