import os
from dotenv import load_dotenv

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
DB_CONN_RETRIES: int = int(os.getenv("DB_CONN_RETRIES", 5))
DB_CONN_RETRY_DELAY: int = int(os.getenv("DB_CONN_RETRY_DELAY", 5))

# --- Application Settings ---
LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO").upper()
TIMEZONE: str = os.getenv("TIMEZONE", "Etc/GMT-3")

# --- Logging Queue & Rotation ---
LOG_QUEUE_INTERVAL_SECONDS: int = int(os.getenv("LOG_QUEUE_INTERVAL_SECONDS", 5))
LOG_QUEUE_BATCH_SIZE: int = int(os.getenv("LOG_QUEUE_BATCH_SIZE", 50))
LOG_ROTATION_ENABLED: bool = os.getenv("LOG_ROTATION_ENABLED", "True").lower() in ('true', '1', 't')
LOG_RETENTION_DAYS: int = int(os.getenv("LOG_RETENTION_DAYS", 30))

# --- Scheduler Settings ---
GC_INTERVAL_SECONDS: int = int(os.getenv("GC_INTERVAL_SECONDS", 3600))
DEPLOY_TYPE: str = os.getenv("DEPLOY_TYPE", "source")
