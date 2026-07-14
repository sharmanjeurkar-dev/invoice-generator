# Use the official Python 3.11 slim image
FROM python:3.11-slim

# Prevent Python from writing .pyc files to disk and buffer output
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
# Ensure Python can find modules in the src/ directory
ENV PYTHONPATH=/app

# --- Lambda-specific: only /tmp is writable at runtime ---
# Playwright/Chromium need somewhere to write profile/cache data, and HOME
# isn't writable inside Lambda's execution environment by default.
ENV HOME=/tmp
ENV XDG_CACHE_HOME=/tmp/.cache
ENV XDG_CONFIG_HOME=/tmp/.config

# Set the working directory inside the container
WORKDIR /app

# Install system dependencies required for PostgreSQL (asyncpg) and Playwright
RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy the requirements file and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip
RUN pip install --no-cache-dir -r requirements.txt

# Lambda Runtime Interface Client — this is what lets a non-AWS base image
# (python:3.11-slim, Debian-based) speak the Lambda invocation protocol.
# Needed because Playwright's apt dependencies are far easier to install on
# Debian than on the Amazon-Linux-based public.ecr.aws/lambda/python image.
RUN pip install --no-cache-dir awslambdaric

# Install Playwright's Chromium browser and its required OS-level dependencies
# Baked into the image at build time — this directory is read-only at
# runtime, which is fine, Chromium just needs the *binary* to be readable;
# its writable scratch space comes from HOME=/tmp set above.
RUN playwright install chromium
RUN playwright install-deps chromium

# Copy the rest of the backend application code into the container
COPY . .

# --- Lambda entrypoint ---
# Replaces `uvicorn ... --host 0.0.0.0 --port 8000`. Lambda doesn't run a
# persistent server listening on a port — the RIC invokes your handler
# function directly per-request.
#
# Requires `handler = Mangum(app)` to exist in src/api/api.py (see below).
ENTRYPOINT ["python", "-m", "awslambdaric"]
CMD ["src.api.api.handler"]