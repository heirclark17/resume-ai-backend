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

# Copy and set permissions for start script
COPY start.sh /start.sh
RUN chmod +x /start.sh

# Expose port
EXPOSE 8000

# Use start script that properly expands PORT variable
CMD ["/start.sh"]
