# MCP Gateway - Docker Image
FROM python:3.12-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements file
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY gateway/ gateway/
COPY lib/ lib/
COPY agents/ agents/

# Set environment variables
ENV PYTHONPATH=/app
ENV GATEWAY_PORT=8000
ENV AWS_REGION=us-west-2
ENV CLOUDMAP_NAMESPACE=a2a-agents.local
ENV PYTHONUNBUFFERED=1

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Run the MCP Gateway
CMD ["python3", "gateway/main.py"]
