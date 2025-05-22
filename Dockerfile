# Use an official Python runtime as a parent image
# python:3.9-slim-bullseye is a good balance of size and compatibility.
FROM python:3.9-slim-bullseye

# Set environment variables for Python
# PYTHONUNBUFFERED: Ensures that Python output is sent straight to terminal without being buffered first.
# PYTHONDONTWRITEBYTECODE: Prevents Python from writing .pyc files to disc (equivalent to python -B).
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Set the working directory in the container
WORKDIR /app

# Update package lists, install git (in case any pip package needs it for compilation from VCS)
# and libpq-dev (required for asyncpg, the PostgreSQL adapter).
# Then, clean up apt cache to reduce image size.
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        git \
        libpq-dev \
        gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy the requirements file into the container at /app
COPY requirements.txt .

# Install Python dependencies
# --no-cache-dir: Disables the pip cache, which can reduce image size.
# -r requirements.txt: Installs packages from the specified requirements file.
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code into the container at /app
# This includes the 'userbot' directory and any other files at the root needed at runtime.
COPY . .

# Specify the command to run on container start
# Runs the userbot module.
# CMD ["python3", "-m", "userbot"]

# The userbot is not started automatically by this Dockerfile.
# This change allows for more flexible startup, especially when using docker-compose
# or when needing to perform setup steps before launching the bot.
#
# To run the userbot after starting a container based on this image:
# 1. If using docker-compose:
#    The docker-compose.yml typically defines the command to run.
#    If not, or if you need to run it manually in an already running service:
#    docker-compose exec <service_name> python3 -m userbot [your_arguments]
#    (e.g., docker-compose exec userbot python3 -m userbot)
#
# 2. If using plain 'docker run':
#    You can specify the command when you run the container:
#    docker run -it --rm <image_name> python3 -m userbot [your_arguments]
#    Or, if the container is already running (e.g., started with -d):
#    docker exec -it <container_name> python3 -m userbot [your_arguments]
#
# Replace <service_name>, <image_name>, or <container_name> appropriately.
# Refer to README.md for available userbot arguments.
