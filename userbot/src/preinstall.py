from userbot.src.config import *
from art import text2art


def preinstall():
    print(text2art('SETUP', font='random', chr_ignore=True))
    
    # Получение значений от пользователя
    api_id = int(input('-> [setup] - Введите API ID: '))
    api_hash = input('-> [setup] - Введите API HASH: ')

    # Запись значений в .env
    with open('.env', 'w') as env_file:
        env_file.write(f'API_ID={api_id}\n')
        env_file.write(f'API_HASH={api_hash}\n')
    
    return api_id, api_hash
