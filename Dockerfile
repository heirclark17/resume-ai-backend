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

# Run the application (Railway sets $PORT dynamically)
CMD uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}
