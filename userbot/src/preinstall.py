from userbot.src.config import *
from art import text2art


def preinstall():
    """
    This function is responsible for preinstalling the application. It prompts the user to input the API ID and API HASH, and stores them in a .env file. The function returns the API ID and API HASH.

    Parameters:
    None

    Returns:
    - api_id (str): The API ID entered by the user.
    - api_hash (str): The API HASH entered by the user.
    """
    print(text2art("SETUP", font="random", chr_ignore=True))

    api_id = input("-> [setup] - Введите API ID: ").strip()
    api_hash = input("-> [setup] - Введите API HASH: ").strip()

    print("\nIMPORTANT SECURITY WARNING:")
    print("API_ID and API_HASH will be stored in plaintext in the .env file.")
    print("Please ensure this file is kept secure and is not exposed, as it provides direct access to your Telegram account.")
    print("Consider using environment variables directly in your deployment for better security.\n")

    with open(".env", "w") as env_file:
        env_file.write(f"API_ID={api_id}\n")
        env_file.write(f"API_HASH={api_hash}\n")

    return api_id, api_hash
