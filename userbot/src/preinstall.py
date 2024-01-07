from userbot.src.config import *
from art import text2art
from userbot.src.encrypt import CryptoUtils
import sys

def preinstall():
   print(text2art('SETUP', font='random', chr_ignore=True))

   api_id = input('-> [setup] - Введите API ID: ').encode(sys.stdin.encoding).decode('utf-8')
   api_hash = input('-> [setup] - Введите API HASH: ').encode(sys.stdin.encoding).decode('utf-8')

   key = CryptoUtils.get_hwid()

   with open('.env', 'w') as env_file:
       env_file.write(f'API_ID={CryptoUtils.encrypt_xor(api_id, key)}\n')
       env_file.write(f'API_HASH={CryptoUtils.encrypt_xor(api_hash, key)}\n')

   return api_id, api_hash
