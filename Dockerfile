# Streamline Government Refinance Agent
# Production Dockerfile for AWS Bedrock AgentCore deployment

FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

WORKDIR /app

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV AWS_REGION=us-east-1
ENV AWS_DEFAULT_REGION=us-east-1
ENV DOCKER_CONTAINER=1

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy dependency files
COPY requirements.txt .

# Install Python dependencies
RUN uv pip install --system --no-cache -r requirements.txt

# Copy application code
COPY . .

# Create non-root user for security (AgentCore requirement)
RUN useradd -m -u 1000 bedrock_agentcore && \
    chown -R bedrock_agentcore:bedrock_agentcore /app

# Switch to non-root user
USER bedrock_agentcore

# Expose ports (AgentCore standard ports)
EXPOSE 9000 8000 8080

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Default command - for local development
CMD ["python", "api.py"]

# For AgentCore production deployment, use:
# CMD ["opentelemetry-instrument", "python", "refi_agent.py"]
