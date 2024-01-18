from userbot.src.config import *
from art import text2art
from userbot.src.encrypt import CryptoUtils
import sys


def preinstall():
    """
    This function is responsible for preinstalling the application. It prompts the user to input the API ID and API HASH, encrypts them using a key obtained from the CryptoUtils module, and stores them in a .env file. The function returns the API ID and API HASH.

    Parameters:
    None

    Returns:
    - api_id (str): The API ID entered by the user.
    - api_hash (str): The API HASH entered by the user.
    """
    print(text2art("SETUP", font="random", chr_ignore=True))

    api_id = (
        input("-> [setup] - Введите API ID: ")
        .encode(sys.stdin.encoding)
        .decode("utf-8")
    )
    api_hash = (
        input("-> [setup] - Введите API HASH: ")
        .encode(sys.stdin.encoding)
        .decode("utf-8")
    )

    with open(".env", "w") as env_file:
        env_file.write(f"API_ID={CryptoUtils.encrypt(api_id)}\n")
        env_file.write(f"API_HASH={CryptoUtils.encrypt(api_hash)}\n")

    return api_id, api_hash
