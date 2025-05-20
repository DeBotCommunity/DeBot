import os
import sys
import base64 # Required for Fernet key format
from cryptography.fernet import Fernet

class EncryptionManager:
    def __init__(self, key: bytes):
        if not key:
            print("Error: Encryption key cannot be empty.", file=sys.stderr)
            sys.exit(1)
        try:
            self.fernet = Fernet(key)
        except Exception as e:
            print(f"Error initializing Fernet with the provided key: {e}", file=sys.stderr)
            print("Please ensure USERBOT_ENCRYPTION_KEY is a valid URL-safe base64-encoded 32-byte key.", file=sys.stderr)
            sys.exit(1)

    def encrypt(self, data: bytes) -> bytes:
        if not isinstance(data, bytes):
            raise TypeError("Data to encrypt must be bytes.")
        return self.fernet.encrypt(data)

    def decrypt(self, token: bytes) -> bytes:
        if not isinstance(token, bytes):
            raise TypeError("Token to decrypt must be bytes.")
        try:
            return self.fernet.decrypt(token)
        except Exception as e: # Broad exception for invalid token, expired, etc.
            print(f"Decryption failed: {e}. This may be due to an incorrect key or corrupted data.", file=sys.stderr)
            # Depending on policy, could raise a custom error
            raise ValueError("Decryption failed. Incorrect key or corrupted data.") from e

    @staticmethod
    def generate_key() -> str:
        # Returns a URL-safe base64-encoded string key
        return Fernet.generate_key().decode('utf-8')

ENCRYPTION_KEY_ENV_VAR = "USERBOT_ENCRYPTION_KEY"
ENCRYPTION_KEY = os.getenv(ENCRYPTION_KEY_ENV_VAR)

if not ENCRYPTION_KEY:
    print(f"Critical Error: The environment variable '{ENCRYPTION_KEY_ENV_VAR}' is not set.", file=sys.stderr)
    print("This variable must contain a valid Fernet encryption key.", file=sys.stderr)
    print(f"You can generate a new key by running: python -c 'from userbot.src.encrypt import EncryptionManager; print(EncryptionManager.generate_key())'", file=sys.stderr)
    sys.exit(1)

try:
    # Ensure the key is bytes for Fernet
    encryption_manager = EncryptionManager(ENCRYPTION_KEY.encode('utf-8'))
except Exception as e:
    # Handles if ENCRYPTION_KEY.encode fails or EncryptionManager init fails
    print(f"Failed to initialize EncryptionManager: {e}", file=sys.stderr)
    sys.exit(1)
