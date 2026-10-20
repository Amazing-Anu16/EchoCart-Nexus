# Multi-stage Dockerfile for EchoCart Nexus MCP Server
# Optimized for AWS Lambda with AWS Lambda Web Adapter

# ---------------------------------------------------------------------------
# Stage 1: Obtain the AWS Lambda Web Adapter binary
# ---------------------------------------------------------------------------
FROM public.ecr.aws/awsguru/aws-lambda-adapter:0.9.0 AS aws-lambda-adapter

# ---------------------------------------------------------------------------
# Stage 2: Production Container with Slim Python 3.12 Base
# ---------------------------------------------------------------------------
FROM python:3.12-slim

# Copy the AWS Lambda Web Adapter to the extensions folder
COPY --from=aws-lambda-adapter /lambda-adapter /opt/extensions/lambda-adapter

# Set environment variables for Lambda Web Adapter and Python runtime
ENV PORT=8080 \
    AWS_LWA_PORT=8080 \
    AWS_LWA_INVOKE_MODE=response_stream \
    AWS_LWA_READINESS_CHECK_PATH=/health \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    ALLOWED_ORIGINS="*"

# Set application working directory
WORKDIR /app

# Install dependencies first for optimal Docker layer caching
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy application source code
COPY . .

# Expose web server port
EXPOSE 8080

# Execute Uvicorn ASGI server
CMD ["python", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]
