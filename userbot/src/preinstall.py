from userbot.src.config import *
from art import text2art
from userbot.src.encrypt import CryptoUtils


def preinstall():
    print(text2art('SETUP', font='random', chr_ignore=True))
    
    api_id = input('-> [setup] - Введите API ID: ')
    api_hash = input('-> [setup] - Введите API HASH: ')

    key = CryptoUtils.get_hwid()

    with open('.env', 'w') as env_file:
        env_file.write(f'API_ID={CryptoUtils.encrypt_xor(api_id, key)}\n')
        env_file.write(f'API_HASH={CryptoUtils.encrypt_xor(api_hash, key)}\n')
    
    return api_id, api_hash
