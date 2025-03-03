# Use an official Python image
FROM python:3.11-slim

# Install ffmpeg and necessary dependencies
RUN apt-get update && apt-get install -y \
    ffmpeg \
    --no-install-recommends \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements file
COPY requirements.txt .

# Install pip and dependencies
RUN python -m ensurepip --upgrade \
    && python -m pip install --upgrade pip \
    && python -m pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Expose port
EXPOSE 8080

# Start the app
CMD ["/usr/local/bin/python", "-m", "uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8080"]
