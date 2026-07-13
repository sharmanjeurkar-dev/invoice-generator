# Use the official Python 3.11 slim image
FROM python:3.11-slim

# Prevent Python from writing .pyc files to disk and buffer output
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
# Ensure Python can find modules in the src/ directory
ENV PYTHONPATH=/app

# Set the working directory inside the container
WORKDIR /app

# Install system dependencies required for PostgreSQL (asyncpg) and Playwright
RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy the requirements file and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright's Chromium browser and its required OS-level dependencies
RUN playwright install chromium
RUN playwright install-deps chromium

# Copy the rest of the backend application code into the container
COPY . .

# Expose the port FastAPI runs on
EXPOSE 8000

# Command to run the application (pointing specifically to src/api/api.py)
CMD ["uvicorn", "src.api.api:app", "--host", "0.0.0.0", "--port", "8000"]