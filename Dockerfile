# Use official Playwright Python image which includes all browsers pre-installed
FROM mcr.microsoft.com/playwright/python:v1.51.0-noble

# Set working directory
WORKDIR /app

# Copy requirements first (for better caching)
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Expose port
EXPOSE 8000

# No CMD - railway.toml startCommand will be used instead
# This allows Railway to properly expand $PORT environment variable
