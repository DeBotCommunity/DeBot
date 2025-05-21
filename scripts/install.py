import os
import subprocess
import sys

# Global prefix for docker commands, can be updated if sudo is needed
DOCKER_COMMAND_PREFIX = ["docker"]
# Not strictly needed as a global due to DOCKER_COMMAND_PREFIX changing, but can be informative.
NEEDS_SUDO_FOR_DOCKER = False

def print_welcome_message():
    print("Welcome to the UserBot autoinstall script!")
    print("This script will attempt to set up your environment.")
    print("-" * 30)

def _run_command(command, check=True, capture_output=False, text=False, suppress_errors=False):
    """Helper function to run subprocess commands."""
    try:
        process = subprocess.run(command, check=check, capture_output=capture_output, text=text)
        return process.stdout.strip() if capture_output and process.stdout else ""
    except subprocess.CalledProcessError as e:
        if not suppress_errors:
            print(f"[ERROR] Command '{' '.join(command)}' failed with exit code {e.returncode}.")
            # Try to decode stderr if it was captured
            stderr_output = ""
            if e.stderr:
                if isinstance(e.stderr, bytes):
                    stderr_output = e.stderr.decode('utf-8', 'replace').strip()
                else: # str
                    stderr_output = e.stderr.strip()
            if stderr_output:
                print(f"[STDERR] {stderr_output}")
        raise
    except FileNotFoundError as e:
        if not suppress_errors:
            print(f"[ERROR] Command not found: {command[0]}. Please ensure it's installed and in your PATH.")
        raise


def install_python_dependencies():
    print("\n[INFO] Installing Python dependencies...")
    requirements_path = os.path.join(os.path.dirname(__file__), "..", "requirements.txt")
    if not os.path.exists(requirements_path):
        print(f"[ERROR] requirements.txt not found at {requirements_path}")
        print("Please ensure the file exists in the project root.")
        return False

    try:
        _run_command([sys.executable, "-m", "pip", "install", "-r", requirements_path])
        print("[SUCCESS] Python dependencies installed successfully.")
        return True
    except subprocess.CalledProcessError:
        # Error message already printed by _run_command
        print("Please try installing them manually using: pip install -r requirements.txt")
        return False
    except FileNotFoundError:
        # Error message already printed by _run_command for pip
        return False


def check_docker_installed():
    print("\n[INFO] Checking Docker installation...")
    try:
        _run_command(["docker", "--version"], capture_output=True, suppress_errors=True)
        print("[INFO] Docker is installed.")
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("[INFO] Docker is not installed.")
        return False

def _try_docker_command(command_args, check=True, capture_output=False, text=False, suppress_errors=False):
    """Tries a docker command without sudo, then with sudo if a permission-like error occurs."""
    global DOCKER_COMMAND_PREFIX, NEEDS_SUDO_FOR_DOCKER
    
    # Initial command attempt
    cmd_to_try = DOCKER_COMMAND_PREFIX + command_args
    try:
        # print(f"Attempting: {' '.join(cmd_to_try)}") # For debugging
        return _run_command(cmd_to_try, check=check, capture_output=capture_output, text=text, suppress_errors=suppress_errors)
    except subprocess.CalledProcessError as e:
        # Check if it's a permission error and sudo is not already being used
        stderr_output = ""
        if e.stderr:
            if isinstance(e.stderr, bytes): stderr_output = e.stderr.decode('utf-8', 'replace').lower()
            else: stderr_output = e.stderr.lower()

        if ("permission denied" in stderr_output or "dial unix /var/run/docker.sock" in stderr_output) and DOCKER_COMMAND_PREFIX[0] != "sudo":
            print("[INFO] Docker command failed with permission error. Retrying with sudo.")
            DOCKER_COMMAND_PREFIX = ["sudo", "docker"]
            NEEDS_SUDO_FOR_DOCKER = True
            cmd_to_retry_with_sudo = DOCKER_COMMAND_PREFIX + command_args
            # print(f"Retrying with: {' '.join(cmd_to_retry_with_sudo)}") # For debugging
            # When retrying with sudo, we let _run_command print errors if it fails again.
            return _run_command(cmd_to_retry_with_sudo, check=check, capture_output=capture_output, text=text, suppress_errors=False)
        else:
            if not suppress_errors:
                 # _run_command would have already printed the error if suppress_errors was False for it.
                 # This ensures an error is noted if the initial _run_command had suppress_errors=True
                 # but the error was not a permission error.
                print(f"[ERROR] Docker command '{' '.join(cmd_to_try)}' failed.")
            raise # Re-raise the original error if not a permission issue or sudo already tried
    except FileNotFoundError:
        # _run_command would have already printed "command not found" for "docker"
        # If DOCKER_COMMAND_PREFIX was ["sudo", "docker"], it means "sudo" was found but "docker" (as part of sudo docker) was not.
        # Or "sudo" itself wasn't found. _run_command handles the "sudo" not found.
        if DOCKER_COMMAND_PREFIX[0] == "sudo" and not suppress_errors:
            print(f"[ERROR] 'sudo docker' command execution failed. Ensure 'docker' is in root's PATH or sudo environment.")
        raise


def check_docker_running():
    print("\n[INFO] Checking if Docker is running...")
    try:
        _try_docker_command(["ps"], suppress_errors=True) # Initial check
        print(f"[INFO] Docker is running (or accessible with {'sudo ' if NEEDS_SUDO_FOR_DOCKER else ''}docker).")
        return True
    except (subprocess.CalledProcessError, FileNotFoundError) as e_initial_check:
        # Initial check failed, if on Linux and Docker seems installed, try to start it
        if "linux" in sys.platform.lower() and check_docker_installed(): # check_docker_installed is quick
            print("[INFO] Docker is not responsive. Attempting to start Docker service on Linux...")
            try:
                # Try common commands to start Docker service
                _run_command(["sudo", "systemctl", "start", "docker"])
                print("[INFO] Attempted 'sudo systemctl start docker'.")
            except (subprocess.CalledProcessError, FileNotFoundError) as e_systemctl:
                print(f"[WARNING] 'sudo systemctl start docker' failed or command not found: {e_systemctl}")
                try:
                    _run_command(["sudo", "service", "docker", "start"])
                    print("[INFO] Attempted 'sudo service docker start'.")
                except (subprocess.CalledProcessError, FileNotFoundError) as e_service:
                    print(f"[WARNING] 'sudo service docker start' failed or command not found: {e_service}")
                    print("[INFO] Could not start Docker service automatically.")
                    # Proceed to final check, which will likely fail and print the error.
            
            # Wait a moment for the service to potentially start
            print("[INFO] Waiting a few seconds for Docker service to initialize...")
            import time
            time.sleep(5) # Give Docker a moment

            # Retry checking Docker status
            print("[INFO] Retrying to check Docker status...")
            try:
                _try_docker_command(["ps"], suppress_errors=False) # This time, don't suppress error messages
                print(f"[INFO] Docker is now running (or accessible with {'sudo ' if NEEDS_SUDO_FOR_DOCKER else ''}docker).")
                return True
            except (subprocess.CalledProcessError, FileNotFoundError):
                print("[ERROR] Docker is still not running or accessible after attempting to start the service.")
                print("Please ensure the Docker daemon is running and you have permissions to access it.")
                return False
        else: # Not Linux, or Docker not even installed
            if NEEDS_SUDO_FOR_DOCKER:
                print("[ERROR] Docker is not running or not accessible. 'sudo docker ps' also failed. Please ensure the Docker daemon is running.")
            else:
                print("[ERROR] Docker is not running or not accessible. Please start Docker and/or check permissions.")
            return False

def install_docker_linux():
    print("\n[INFO] Attempting to install Docker on Linux...")
    try:
        _run_command(["sudo", "apt-get", "update"])
        _run_command(["sudo", "apt-get", "install", "-y", "docker-ce", "docker-ce-cli", "containerd.io"])
        print("[SUCCESS] Docker installed successfully via apt-get.")
        current_user = ""
        try:
            current_user = os.getlogin()
        except OSError: # os.getlogin() fails if no controlling tty
            current_user = subprocess.check_output(["whoami"]).decode('utf-8').strip()

        if current_user:
            try:
                _run_command(["sudo", "usermod", "-aG", "docker", current_user])
                print(f"[INFO] Added user '{current_user}' to the docker group.")
                print("[IMPORTANT] You may need to log out and log back in for this change to take full effect (to run Docker without sudo).")
                print("[INFO] For the remainder of this script, 'sudo' might still be used for Docker commands if needed based on current session permissions.")
            except subprocess.CalledProcessError as e:
                print(f"[WARNING] Failed to add user '{current_user}' to docker group: {e}. You may need to run docker commands with sudo or add the user manually.")
        else:
            print("[WARNING] Could not determine current user to add to docker group.")
        return True
    except subprocess.CalledProcessError:
        print("Please install Docker manually. Visit https://docs.docker.com/engine/install/")
        return False
    except FileNotFoundError: # sudo or apt-get not found
        print("[ERROR] sudo or apt-get command not found. Cannot attempt automatic Docker installation.")
        print("Please install Docker manually. Visit https://docs.docker.com/engine/install/")
        return False


def setup_docker_and_postgresql():
    print("\n[INFO] Setting up Docker and PostgreSQL...")
    docker_installed_check = check_docker_installed() # This only checks if 'docker' command exists

    if os.name == 'nt': # Windows
        print("[INFO] Running on Windows.")
        if not docker_installed_check:
            print("[IMPORTANT] Docker Desktop for Windows needs to be installed manually.")
            print("Please download it from https://www.docker.com/products/docker-desktop and install it.")
            # We can't proceed if it's not even installed.
            return False
        # If 'docker' command exists, check_docker_running will see if we can connect
        if not check_docker_running():
            return False
    elif os.name == 'posix': # Linux/macOS
        print(f"[INFO] Running on a POSIX system ({sys.platform}).")
        if not docker_installed_check: # 'docker' command not found
            if "linux" in sys.platform.lower():
                print("[INFO] Docker command not found, attempting installation for Linux...")
                if not install_docker_linux():
                    return False
                # After potential installation, DOCKER_COMMAND_PREFIX might have been set to use sudo
                # We must now check if it's running and accessible
                if not check_docker_running():
                    print("[ERROR] Docker was installed, but it's not running or accessible. Please check the Docker service and permissions.")
                    return False
            else: # macOS or other non-Linux POSIX
                 print("[IMPORTANT] Docker command not found. Docker needs to be installed manually on this OS (e.g., Docker Desktop for Mac).")
                 print("Please download it from https://www.docker.com/products/docker-desktop and install it.")
                 return False # Cannot proceed without Docker
        else: # Docker command is found, now check if it's running/accessible
            if not check_docker_running():
                return False
    else:
        print(f"[WARNING] Unsupported OS: {os.name}. Docker setup might require manual intervention.")
        if not docker_installed_check or not check_docker_running(): # check_docker_running implies installed
            print("[ERROR] Docker is not installed or not running/accessible. Please ensure Docker is set up correctly.")
            return False

    # At this point, Docker should be installed and DOCKER_COMMAND_PREFIX is set correctly.
    print("\n[INFO] Pulling PostgreSQL Docker image (postgres:latest)...")
    try:
        _try_docker_command(["pull", "postgres:latest"])
        print("[SUCCESS] PostgreSQL image pulled successfully.")
    except (subprocess.CalledProcessError, FileNotFoundError):
        print(f"[ERROR] Failed to pull PostgreSQL image using '{' '.join(DOCKER_COMMAND_PREFIX)} pull'.")
        print("Please ensure Docker has internet access and you can pull images from Docker Hub.")
        return False

    container_name = "userbot_postgres_db"
    db_user = "userbot_db_user"
    db_pass = "userbot_db_pass" 
    db_name = "userbot_db"
    db_volume_name = "userbot_postgres_data"

    # Check if a container with the same name already exists
    try:
        existing_container = _try_docker_command(["ps", "-a", "--filter", f"name={container_name}", "--format", "{{.Names}}"], capture_output=True, text=True, suppress_errors=True)
        if existing_container == container_name:
            print(f"[INFO] A Docker container named '{container_name}' already exists.")
            print(f"[INFO] Attempting to stop and remove existing container '{container_name}'...")
            try:
                _try_docker_command(["stop", container_name])
                _try_docker_command(["rm", container_name])
                print(f"[SUCCESS] Existing container '{container_name}' stopped and removed.")
            except (subprocess.CalledProcessError, FileNotFoundError):
                print(f"[ERROR] Failed to stop/remove existing container '{container_name}'.")
                print(f"Please remove it manually using '{' '.join(DOCKER_COMMAND_PREFIX)} stop {container_name} && {' '.join(DOCKER_COMMAND_PREFIX)} rm {container_name}' and rerun the script.")
                return False
    except (subprocess.CalledProcessError, FileNotFoundError):
        # If `docker ps` fails here, it's a problem beyond just the container not existing.
        # check_docker_running should have caught general docker accessibility issues.
        # This might indicate a more specific problem if it occurs.
        print(f"[WARNING] Could not check for existing Docker containers using '{' '.join(DOCKER_COMMAND_PREFIX)} ps'. This might be okay if the command is generally working.")
        pass # Assuming it's okay if the container just doesn't exist.

    print(f"\n[INFO] Creating Docker volume '{db_volume_name}' for data persistence if it doesn't exist...")
    try:
        _try_docker_command(["volume", "create", db_volume_name])
        print(f"[SUCCESS] Docker volume '{db_volume_name}' ensured.")
    except (subprocess.CalledProcessError, FileNotFoundError):
        print(f"[ERROR] Failed to create Docker volume '{db_volume_name}' using '{' '.join(DOCKER_COMMAND_PREFIX)} volume create'.")
        return False

    print(f"\n[INFO] Running PostgreSQL container '{container_name}'...")
    try:
        docker_run_cmd_args = [
            "run", "-d",
            "--name", container_name,
            "-e", f"POSTGRES_USER={db_user}",
            "-e", f"POSTGRES_PASSWORD={db_pass}",
            "-e", f"POSTGRES_DB={db_name}",
            "-p", "5432:5432",
            "-v", f"{db_volume_name}:/var/lib/postgresql/data",
            "postgres:latest"
        ]
        _try_docker_command(docker_run_cmd_args)
        print(f"[SUCCESS] PostgreSQL container '{container_name}' started successfully.")
    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        print(f"[ERROR] Failed to run PostgreSQL container using '{' '.join(DOCKER_COMMAND_PREFIX)} run ...'.")
        print("This might be due to port 5432 already being in use on your host, or other Docker issues.")
        print(f"Check Docker logs for container '{container_name}' for more details ({' '.join(DOCKER_COMMAND_PREFIX)} logs {container_name}).")
        # Attempt to print docker logs for the container if it was created but failed to start
        if isinstance(e, subprocess.CalledProcessError): # Only if 'run' command itself was found
            try:
                logs = _try_docker_command(["logs", container_name], capture_output=True, text=True, check=False, suppress_errors=True)
                if logs:
                    print(f"\n--- Logs from container '{container_name}' ---")
                    print(logs)
                    print("--- End of logs ---")
            except Exception as log_e:
                print(f"[INFO] Could not retrieve logs for container '{container_name}': {log_e}")
        return False

    print("\n--- PostgreSQL Connection Details ---")
    print("Your PostgreSQL database should now be running in a Docker container.")
    print(f"  Container Name: {container_name}")
    print(f"  Username:       {db_user}")
    print(f"  Password:       {db_pass} (Please change this in a production environment!)")
    print(f"  Database Name:  {db_name}")
    print(f"  Host:           localhost (or your Docker host IP if not local)")
    print(f"  Port:           5432 (or the host port you mapped if you changed it)")
    print("\nTo connect your UserBot, you might need to set environment variables like:")
    print(f"  DATABASE_URL=postgresql://{db_user}:{db_pass}@localhost:5432/{db_name}")
    print("------------------------------------")
    return True

def run_smoke_test():
    print("\n[INFO] Running basic smoke test...")
    try:
        # Attempt to add project root to Python path for imports
        # This assumes 'scripts/' is one level down from project root.
        project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        if project_root not in sys.path:
            sys.path.insert(0, project_root)
            print(f"[INFO] Added project root {project_root} to sys.path for smoke test.")

        print("[INFO] Attempting to import 'userbot'...")
        import userbot
        print("[SUCCESS] Imported 'userbot' module successfully.")

        print("[INFO] Attempting to import and initialize 'userbot.src.config.Config'...")
        # To prevent Config from trying to load a non-existent file or exit,
        # we can temporarily mock 'sys.exit' if Config calls it on init failure.
        # However, a better approach for a smoke test is to see if it *can* be initialized,
        # assuming a default/empty config might be okay or it handles missing file gracefully.
        # For this test, we'll assume it might raise an exception on failure, or we check a property.
        # We also need to ensure that the UserBot's own dependencies for config (like dotenv) are present.
        
        # Create a dummy .env or config.ini if Config class strictly requires one for initialization
        # For a smoke test, it's better if Config can init without a file or with a dummy one.
        # Let's assume userbot.src.config.Config can be instantiated.
        from userbot.src.config import Config
        config_instance = Config() # This might need specific env vars or a config file
        
        # A simple check could be if the instance is not None, or if a known default property exists.
        if config_instance is not None:
            print("[SUCCESS] Initialized 'userbot.src.config.Config' successfully.")
            # You could add a more specific check here if needed, e.g.,
            # if hasattr(config_instance, 'some_default_attribute'):
            #     print("[SUCCESS] Config instance seems valid.")
            # else:
            #     print("[WARNING] Config instance created, but might not be fully valid (missing expected attribute).")
            #     return False # Or treat as partial success depending on strictness
            return True
        else:
            print("[FAILURE] Failed to initialize 'userbot.src.config.Config' (instance is None).")
            return False

    except ImportError as e:
        print(f"[FAILURE] Smoke test failed: Could not import module. Error: {e}")
        import traceback
        traceback.print_exc()
        return False
    except SystemExit as e:
        print(f"[FAILURE] Smoke test failed: The UserBot code called sys.exit(). Exit code: {e.code}")
        print("This usually indicates a critical configuration error (e.g., missing essential environment variables).")
        print("Please check the output above from the UserBot's own error messages.")
        return False
    except Exception as e:
        print(f"[FAILURE] Smoke test failed: Error during Config initialization or other operation. Error: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    print_welcome_message()
    dependencies_installed = False
    smoke_test_passed = False
    overall_success = True # Assume true initially

    if install_python_dependencies():
        dependencies_installed = True
        # Run smoke test only if dependencies are installed
        if run_smoke_test():
            smoke_test_passed = True
        else:
            overall_success = False # Smoke test failure means overall failure
            print("[WARNING] Smoke test failed. UserBot may not be configured correctly or core components are missing.")
    else:
        overall_success = False # Dependency failure means overall failure
        print("[WARNING] Python dependency installation failed. Skipping smoke test. UserBot may not run.")

    # Docker setup can proceed even if smoke test failed, but overall_success reflects all critical steps
    if not setup_docker_and_postgresql():
        overall_success = False
        print("[INFO] PostgreSQL/Docker setup failed or was skipped.")


    print("-" * 30)
    if overall_success:
        print("\n[SUCCESS] Autoinstall script completed. Core components seem okay.")
        if dependencies_installed and smoke_test_passed:
             print("Python dependencies installed and basic smoke test passed.")
        if NEEDS_SUDO_FOR_DOCKER:
            print("[INFO] Note: Docker commands were executed using 'sudo'.")
        print("Please ensure you have a valid 'config.ini' or set appropriate environment variables for the UserBot to run fully.")
    else:
        print("\n[FAILURE] Autoinstall script completed, but some critical steps failed.")
        if not dependencies_installed:
            print("Critical issue: Python dependencies did not install correctly.")
        elif not smoke_test_passed:
            print("Critical issue: Basic smoke test failed. UserBot core components might be broken or misconfigured.")
        print("Please review the output above for specific error messages and manual resolution steps.")
    sys.exit(0 if overall_success else 1)


if __name__ == "__main__":
    # The script assumes requirements.txt is in the parent directory.
    # install_python_dependencies will report if requirements.txt is missing.
    main()
