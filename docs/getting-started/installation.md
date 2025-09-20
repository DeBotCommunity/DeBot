# Установка и настройка

Прежде чем начать, убедитесь, что на вашем сервере или локальной машине установлены **Docker** и **Docker Compose**.

Мы предлагаем два способа установки. Для большинства пользователей мы настоятельно рекомендуем первый способ.

---

### Способ 1: Использование Docker-образа (Рекомендуется)

Этот метод **не требует скачивания (клонирования) исходного кода**. Вам нужно лишь создать два конфигурационных файла и запустить одну команду.

#### Шаг 1: Создайте рабочую директорию

Создайте папку, где будут храниться ваши настройки и данные.

```bash
mkdir my_debot
cd my_debot
```

#### Шаг 2: Создайте файл `docker-compose.yml`

Внутри папки `my_debot` создайте файл с именем `docker-compose.yml` и скопируйте в него следующее содержимое:

```yaml
services:
  userbot:
    # Указываем готовый образ из Docker Hub
    image: debotcommunity/debot:latest
    container_name: debot_userbot
    env_file:
      - .env
    restart: unless-stopped
    volumes:
      # Эта папка будет создана на вашем хосте для хранения модулей
      - ./userbot/modules:/app/userbot/modules
    depends_on:
      - db
    command: ["python3", "-m", "userbot"]

  db:
    image: postgres:13-alpine
    container_name: debot_postgres
    environment:
      POSTGRES_USER: ${DB_USER}
      POSTGRES_PASSWORD: ${DB_PASS}
      POSTGRES_DB: ${DB_NAME}
    volumes:
      - postgres_data:/var/lib/postgresql/data
    ports:
      - "${DB_PORT}:5432"
    restart: unless-stopped

volumes:
  postgres_data:
```

#### Шаг 3: Создайте файл `.env`

Рядом с `docker-compose.yml` создайте файл `.env` для ваших секретных настроек.

1.  **Сгенерируйте ключ шифрования.** Выполните эту команду в терминале, чтобы получить уникальный ключ. Он нужен для защиты ваших сессий.

    ```bash
    python3 -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())'
    ```

2.  **Создайте файл `.env`** и заполните его по шаблону ниже. Замените `<...>` на ваши значения.

    ```env
    # --- Telegram Core Credentials ---
    # Получите их на https://my.telegram.org
    API_ID=<ВАШ_API_ID>
    API_HASH=<ВАШ_API_HASH>

    # --- Security ---
    # Вставьте сюда ключ, сгенерированный на предыдущем шаге
    USERBOT_ENCRYPTION_KEY=<ВАШ_СГЕНЕРИРОВАННЫЙ_КЛЮЧ>

    # --- Database Connection ---
    # Эти значения должны совпадать с секцией 'db' в docker-compose.yml
    DB_HOST=db
    DB_PORT=5432
    DB_NAME=userbot_db
    DB_USER=userbot
    DB_PASS=my_strong_password_123 # Замените на свой надежный пароль!

    # --- Application Settings (можно оставить по умолчанию) ---
    LOG_LEVEL=INFO
    GC_INTERVAL_SECONDS=60
    ```

#### Шаг 4: Запустите DeBot

Теперь, когда оба файла готовы, выполните одну команду:

```bash
docker-compose up -d
```

Docker скачает готовый образ DeBot, образ PostgreSQL и запустит всё в фоновом режиме.

**Готово!** Переходите к [следующему шагу: добавлению вашего первого аккаунта](docs/getting-started/first-run.md).

---

### Способ 2: Установка из исходного кода (Для разработчиков)

Этот метод предназначен для тех, кто хочет изменять исходный код DeBot.

1.  **Клонируйте репозиторий:**
    ```bash
    git clone https://github.com/DeBotCommunity/DeBot.git
    cd DeBot
    ```
2.  **Запустите интерактивный скрипт настройки:**
    Скрипт сам задаст все необходимые вопросы и сгенерирует для вас `docker-compose.yml` и `.env`.
    ```bash
    python3 -m scripts.setup
    ```
3.  **Запустите DeBot:**
    ```bash
    docker-compose up -d --build
    ```
