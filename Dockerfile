# Use the specified Python version
FROM python:3.10.11-slim

# Set the working directory in the container
WORKDIR /app

# Copy the requirements file into the container
COPY requirements.txt .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code into the container
COPY . .

# Command to run the userbot when the container starts
# The --accounts flag should be provided via docker-compose `command` override
CMD ["python3", "-m", "userbot"]
