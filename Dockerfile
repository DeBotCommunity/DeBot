# Stage 1: Build stage
FROM python:3.10.11-alpine AS builder

WORKDIR /app

# Install build dependencies
RUN apk add --no-cache build-base libffi-dev openssl-dev

# Copy requirements and install them
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Stage 2: Final stage
FROM python:3.10.11-alpine

WORKDIR /app

# Install runtime dependencies, including git for module management
RUN apk add --no-cache libffi openssl git

# Copy installed packages from the builder stage
COPY --from=builder /usr/local/lib/python3.10/site-packages/ /usr/local/lib/python3.10/site-packages/
COPY --from=builder /usr/local/bin/ /usr/local/bin/

# Copy the application source code
COPY . .

# Create the modules directory if it doesn't exist
RUN mkdir -p /app/userbot/modules

# Set the entrypoint
CMD ["python3", "-m", "userbot"]
