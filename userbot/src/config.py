import os
from dotenv import load_dotenv
# from userbot.src.encrypt import CryptoUtils # Removed old CryptoUtils import

# Load environment variables from .env file
load_dotenv()

# API credentials for Telegram
API_ID_ENV: str = "API_ID"
API_HASH_ENV: str = "API_HASH"

# Retrieve API credentials
API_ID: str = os.getenv(API_ID_ENV) # These will be loaded as strings
API_HASH: str = os.getenv(API_HASH_ENV) # These will be loaded as strings

# Decrypt API credentials - REMOVED
# The old CryptoUtils decryption block is removed.
# API_ID and API_HASH are now used as plaintext at runtime after loading from .env.
# The new EncryptionManager will handle encryption/decryption for data stored in the database.
# For Telethon client, API_ID (as int) and API_HASH (as str) are used directly.
# Type conversion for API_ID to int happens in userbot/__init__.py before client instantiation.

# Directory where modules are stored
MODULE_FOLDER: str = "userbot.modules"

# Custom alphabet for aesthetic purposes
ALPHABET: dict = {
    "а": "ᴀ",
    "б": "б",
    "в": "ʙ",
    "г": "ᴦ",
    "д": "д",
    "е": "ᴇ",
    "ё": "ё",
    "ж": "ж",
    "з": "з",
    "и": "и",
    "к": "ᴋ",
    "л": "ᴧ",
    "м": "ʍ",
    "н": "н",
    "о": "о",
    "п": "ᴨ",
    "р": "ᴩ",
    "с": "ᴄ",
    "т": "ᴛ",
    "у": "у",
    "ф": "ɸ",
    "х": "х",
    "ц": "ц",
    "ч": "ч",
    "ш": "ɯ",
    "щ": "щ",
    "ъ": "ъ",
    "ь": "ь",
    "э": "϶",
    "ю": "ю",
    "я": "я",
    "q": "ǫ",
    "w": "ᴡ",
    "e": "ᴇ",
    "r": "ʀ",
    "t": "ᴛ",
    "y": "ʏ",
    "u": "ᴜ",
    "i": "ɪ",
    "o": "ᴏ",
    "p": "ᴘ",
    "a": "ᴀ",
    "s": "s",
    "d": "ᴅ",
    "f": "ꜰ",
    "g": "ɢ",
    "h": "ʜ",
    "j": "ᴊ",
    "k": "ᴋ",
    "l": "ʟ",
    "z": "ᴢ",
    "x": "x",
    "c": "ᴄ",
    "v": "ᴠ",
    "b": "ʙ",
    "n": "ɴ",
    "m": "ᴍ",
}