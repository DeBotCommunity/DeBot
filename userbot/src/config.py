import os
from dotenv import load_dotenv
from userbot.src.encrypt import CryptoUtils

# Load environment variables from .env file
load_dotenv()

# Retrieve hardware ID for encryption purposes
key: str = CryptoUtils.get_hwid()

# API credentials for Telegram
API_ID_ENV: str = 'API_ID'
API_HASH_ENV: str = 'API_HASH'

api_id: str = os.getenv(API_ID_ENV)
api_hash: str = os.getenv(API_HASH_ENV)

# Decrypt API credentials
if api_id is not None or api_hash is not None:
    api_id = CryptoUtils.decrypt_xor(api_id, key)
    api_hash = CryptoUtils.decrypt_xor(api_hash, key)

# Directory where modules are stored
MODULE_FOLDER: str = 'userbot.modules'

# Custom alphabet for aesthetic purposes
ALPHABET: dict = {
    "а": "ᴀ", "б": "б", "в": "ʙ", "г": "ᴦ", "д": "д",
    "е": "ᴇ", "ё": "ё", "ж": "ж", "з": "з", "и": "и",
    "к": "ᴋ", "л": "ᴧ", "м": "ʍ", "н": "н", "о": "о",
    "п": "ᴨ", "р": "ᴩ", "с": "ᴄ", "т": "ᴛ", "у": "у",
    "ф": "ɸ", "х": "х", "ц": "ц", "ч": "ч", "ш": "ɯ",
    "щ": "щ", "ъ": "ъ", "ь": "ь", "э": "϶", "ю": "ю",
    "я": "я", "q": "ǫ", "w": "ᴡ", "e": "ᴇ", "r": "ʀ",
    "t": "ᴛ", "y": "ʏ", "u": "ᴜ", "i": "ɪ", "o": "ᴏ",
    "p": "ᴘ", "a": "ᴀ", "s": "s", "d": "ᴅ", "f": "ꜰ",
    "g": "ɢ", "h": "ʜ", "j": "ᴊ", "k": "ᴋ", "l": "ʟ",
    "z": "ᴢ", "x": "x", "c": "ᴄ", "v": "ᴠ", "b": "ʙ",
    "n": "ɴ", "m": "ᴍ"
}
