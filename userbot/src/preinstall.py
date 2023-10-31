from userbot.src.config import *
from art import text2art
import os

def preinstall():
    print(text2art('SETUP', font='random', chr_ignore=True))
    api_id = int(input('-> [setup] - Введите API ID: '))
    api_hash = input('-> [setup] - Введите API HASH: ')

    # Читаем существующий файл
    with open(f'{os.getcwd()}\\userbot\\src\\config.py', 'r', encoding='utf-8') as config_file:
        config_lines = config_file.readlines()

    # Заменяем значения переменных
    for i in range(len(config_lines)):
        if config_lines[i].startswith('api_id'):
            config_lines[i] = f'api_id = \'{api_id}\'\n'
        elif config_lines[i].startswith('api_hash'):
            config_lines[i] = f'api_hash = \'{api_hash}\'\n'

    # Записываем обновленный файл
    with open(f'{os.getcwd()}\\userbot\\src\\config.py', 'w', encoding='utf-8') as config_file:
        config_file.writelines(config_lines)
    return api_id, api_hash
