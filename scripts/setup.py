import os
import sys
import secrets
import string
import re
from pathlib import Path

# Ensure the script can find userbot modules
project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from userbot.src.encrypt import EncryptionManager

def prompt_user(prompt_text: str, default: str = None) -> str:
    """Prompts the user for input with an optional default value."""
    if default:
        return input(f"-> {prompt_text} [default: {default}]: ").strip() or default
    return input(f"-> {prompt_text}: ").strip()

def generate_secure_string(length: int = 16) -> str:
    """Generates a random, secure string for passwords."""
    alphabet = string.ascii_letters + string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(length))

def main():
    """Main setup function to generate docker-compose.yml and .env files."""
    print("--- DeBot Interactive Setup ---")
    
    deploy_type = ""
    while deploy_type not in ["source", "image"]:
        deploy_type = prompt_user("Enter deployment type ('source' for local build, 'image' for pre-built)", "source")

    print("\n--- PostgreSQL Database Configuration ---")
    use_docker_db = prompt_user("Run PostgreSQL in a Docker container?", "yes").lower().startswith('y')
    
    if use_docker_db:
        db_host = "db"
        print("Database will run in Docker. Host will be set to 'db'.")
    else:
        db_host = prompt_user("Enter external database host", "localhost")
        
    db_port = prompt_user("Database port", "5432")
    db_name = prompt_user("Database name", "userbot_db")
    db_user = prompt_user("Database user", "userbot")
    db_pass = prompt_user("Database password (leave empty to generate)", generate_secure_string())
    
    print("\n--- Userbot Core Configuration ---")
    api_id = prompt_user("Enter your Telegram API_ID (used for adding accounts if needed)")
    api_hash = prompt_user("Enter your Telegram API_HASH")
    
    print("\n[SECURITY] Generating a new encryption key for sensitive data...")
    encryption_key = EncryptionManager.generate_key()
    print(f"Your new USERBOT_ENCRYPTION_KEY is: {encryption_key}")
    
    env_content = [
        '# --- Deployment Settings ---',
        f'DEPLOY_TYPE={deploy_type}',
        '',
        '# --- Telegram Core Credentials (for setup/helpers) ---',
        f'API_ID={api_id}',
        f'API_HASH={api_hash}',
        '',
        '# --- Security ---',
        f'USERBOT_ENCRYPTION_KEY={encryption_key}',
        '',
        '# --- Database Connection ---',
        f'DB_TYPE=postgresql',
        f'DB_HOST={db_host}',
        f'DB_PORT={db_port}',
        f'DB_NAME={db_name}',
        f'DB_USER={db_user}',
        f'DB_PASS={db_pass}',
        '',
        '# --- Application Settings ---',
        'LOG_LEVEL=INFO',
        'GC_INTERVAL_SECONDS=60',
        '',
        '# --- Auto Update (only for "image" deployment) ---',
        'AUTO_UPDATE_ENABLED=False',
        'AUTO_UPDATE_INTERVAL_MINUTES=1440',
    ]
    
    env_file_path = project_root / ".env"
    with open(env_file_path, "w") as f:
        f.write("\n".join(env_content) + "\n")
    print(f"\n✅ Configuration saved to: {env_file_path}")

    template_path = project_root / "docker-compose.template.yml"
    if not template_path.exists():
        print(f"❌ Error: docker-compose.template.yml not found at {template_path}")
        return

    with open(template_path, "r") as f:
        compose_template = f.read()

    userbot_service_definition = "build: ." if deploy_type == "source" else f"image: whn0thacked/debot:latest"
    compose_content = compose_template.replace("${USERBOT_SERVICE_DEFINITION}", userbot_service_definition)

    if not use_docker_db:
        # Remove the 'db' service and dependencies on it
        compose_content = re.sub(r'^\s*depends_on:.*?service_healthy\s*$', '', compose_content, flags=re.DOTALL | re.MULTILINE)
        compose_content = re.sub(r'^\s*db:.*?(?=\n\S|\Z)', '', compose_content, flags=re.DOTALL | re.MULTILINE)
        # Remove the volumes key if it's now empty and only contains postgres_data
        compose_content = re.sub(r'^\s*volumes:\s*\n\s*postgres_data:\s*$', '', compose_content, flags=re.MULTILINE)

    compose_file_path = project_root / "docker-compose.yml"
    with open(compose_file_path, "w") as f:
        f.write(compose_content.strip() + "\n")
    print(f"✅ Docker Compose file generated: {compose_file_path}")

    print("\n--- Setup Complete! ---")
    print("To start the userbot, run: 'docker compose up -d'")
    print("To add your first account, use the management script:")
    print(f"\n  docker compose exec userbot python3 -m scripts.manage_account add <account_name>\n")
    print("After adding an account, restart the bot to activate the new session:")
    print("\n  docker compose restart userbot\n")

if __name__ == "__main__":
    main()
