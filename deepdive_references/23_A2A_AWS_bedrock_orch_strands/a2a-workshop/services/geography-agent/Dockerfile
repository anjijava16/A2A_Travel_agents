# Geography Agent - Docker Image
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
COPY agents/ agents/
COPY lib/ lib/
COPY config/ config/
COPY data/ data/

# Set environment variables
ENV PYTHONPATH=/app
ENV AGENT_TYPE=geography-agent
ENV AGENT_NAME=geography-agent
ENV AGENT_PORT=8000
ENV AWS_REGION=us-west-2
ENV CLOUDMAP_NAMESPACE=a2a-agents.local
ENV PYTHONUNBUFFERED=1

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Run the agent using the common launcher
CMD ["python3", "-m", "lib.agents.agent_launcher", "--agent-type", "geography-agent"]
