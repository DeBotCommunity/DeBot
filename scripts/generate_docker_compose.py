import argparse
import secrets
import string
import os

def generate_password(length=12):
    """Generates a random strong password."""
    alphabet = string.ascii_letters + string.digits + string.punctuation
    # Ensure the password contains at least one of each character type for strength, though secrets.choice is usually good enough.
    # This is a simple way, more robust methods might be needed for high security.
    while True:
        password = ''.join(secrets.choice(alphabet) for i in range(length))
        if (any(c.islower() for c in password) and
            any(c.isupper() for c in password) and
            any(c.isdigit() for c in password) and
            any(c.isspace() or c in string.punctuation for c in password)): # check for special char or space
            break
    return password

def main():
    parser = argparse.ArgumentParser(description="Generate docker-compose.yml for PostgreSQL.")
    parser.add_argument("--pg-version", default="latest", help="PostgreSQL version (default: latest)")
    parser.add_argument("--db-name", default="userbot_db", help="Database name (default: userbot_db)")
    parser.add_argument("--username", default="userbot", help="Username (default: userbot)")
    parser.add_argument("--password", help="Password (default: auto-generated)")
    parser.add_argument("--port", type=int, default=5432, help="Port to expose (default: 5432)")
    parser.add_argument(
        "--output-path",
        default="docker-compose.yml",
        help="Path to output the docker-compose.yml file (default: docker-compose.yml in the current directory)",
    )

    args = parser.parse_args()

    actual_password = args.password
    password_was_generated = False
    if not actual_password:
        actual_password = generate_password()
        password_was_generated = True

    docker_compose_content = f"""\
version: '3.8'

services:
  postgres_db:
    image: postgres:{args.pg_version}
    container_name: postgres_db_container
    environment:
      POSTGRES_USER: {args.username}
      POSTGRES_PASSWORD: {actual_password}
      POSTGRES_DB: {args.db_name}
    ports:
      - "{args.port}:5432"
    volumes:
      - pg_data:/var/lib/postgresql/data
    restart: unless-stopped

volumes:
  pg_data:
"""

    output_file_path = args.output_path
    try:
        with open(output_file_path, "w") as f:
            f.write(docker_compose_content)
        print(f"Successfully generated {output_file_path}")
        if password_was_generated:
            print(f"Generated password: {actual_password}")
            print("Please save this password securely.")
        print(f"To start the service, run: docker-compose -f {output_file_path} up -d")

    except IOError as e:
        print(f"Error writing to file {output_file_path}: {e}")

if __name__ == "__main__":
    main()
