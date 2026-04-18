FROM python:3.11-slim

# Prevent Python from writing .pyc files and enable buffering for logging
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

WORKDIR /app

# Install system dependencies if needed (none strictly required for transcript-api)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Expore Port (Render handles mapping, but we default to 10000)
EXPOSE 10000

# Start application
CMD ["python", "main.py"]
