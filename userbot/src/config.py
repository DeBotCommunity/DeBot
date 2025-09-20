import os
from dotenv import load_dotenv
from typing import Dict

# Load environment variables from .env file
load_dotenv()

# --- Core Credentials ---
API_ID: str = os.getenv("API_ID")
API_HASH: str = os.getenv("API_HASH")

# --- Database Connection ---
DB_TYPE: str = os.getenv("DB_TYPE", "postgresql")
DB_HOST: str = os.getenv("DB_HOST", "localhost")
DB_PORT: int = int(os.getenv("DB_PORT", 5432))
DB_USER: str = os.getenv("DB_USER", "userbot")
DB_PASS: str = os.getenv("DB_PASS", "userbot_password")
DB_NAME: str = os.getenv("DB_NAME", "userbot_db")

# --- Application Settings ---
MODULE_FOLDER: str = "userbot.modules"
LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO").upper()

# --- Scheduler Settings ---
GC_INTERVAL_SECONDS: int = int(os.getenv("GC_INTERVAL_SECONDS", 30))
AUTO_UPDATE_ENABLED: bool = os.getenv("AUTO_UPDATE_ENABLED", "False").lower() in ('true', '1', 't')
AUTO_UPDATE_INTERVAL_MINUTES: int = int(os.getenv("AUTO_UPDATE_INTERVAL_MINUTES", 1440))
DEPLOY_TYPE: str = os.getenv("DEPLOY_TYPE", "source") # 'source' or 'image'
