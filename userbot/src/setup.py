from userbot.src.config import *
from art import text2art
from userbot.src.encrypt import CryptoUtils
from userbot import logger


def setup():
    """
    This function is responsible for setup the application. It prompts the user to input the API ID and API HASH, encrypts them using a key obtained from the CryptoUtils module, and stores them in a .env file. The function returns the API ID and API HASH.

    Parameters:
    None

    Returns:
    - api_id (str): The API ID entered by the user.
    - api_hash (str): The API HASH entered by the user.
    """
    setup_art = text2art("SETUP", font="random", chr_ignore=True)
    print(f"\033[33m{setup_art}\033[0m")

    api_id = input("-> [setup] - Введите API ID: ").strip()
    api_hash = input("-> [setup] - Введите API HASH: ").strip()

    logger.info("### Создание Docker-compose.yaml для развертывания PostgreSQL")

    postgres_user = input("-> [setup] - Введите имя пользователя базы данных: ").strip()
    postgres_password = input(
        "-> [setup] - Введите пароль пользователя базы данных: "
    ).strip()
    postgres_db = input("-> [setup] - Введите имя базы данных: ").strip()

    dockerfile_content = """
services:
  database:
    image: postgres
    ports:
      - "5432:5432"
    restart: always
    environment:
      POSTGRES_USER: POSTGRES_USER
      POSTGRES_PASSWORD: POSTGRES_PASSWORD
      POSTGRES_DB: POSTGRES_DB
"""

    dockerfile_content = dockerfile_content.replace("POSTGRES_USER", postgres_user)
    dockerfile_content = dockerfile_content.replace(
        "POSTGRES_PASSWORD", postgres_password
    )
    dockerfile_content = dockerfile_content.replace("POSTGRES_DB", postgres_db)

    with open("Docker-compose.yaml", "w") as dockerfile:
        dockerfile.write(dockerfile_content)

    with open(".env", "w") as env_file:
        env_file.write(f"API_ID={CryptoUtils.encrypt(api_id)}\n")
        env_file.write(f"API_HASH={CryptoUtils.encrypt(api_hash)}\n")

    return api_id, api_hash
