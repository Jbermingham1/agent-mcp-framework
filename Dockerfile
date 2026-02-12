# Multi-stage Dockerfile for agent-mcp-framework
# Stage 1: Build dependencies
FROM python:3.12-slim AS builder

WORKDIR /app

# Install build dependencies
RUN pip install --no-cache-dir hatchling

# Copy project files
COPY pyproject.toml README.md LICENSE ./
COPY src/ src/

# Build wheel
RUN pip wheel --no-deps --wheel-dir /wheels .

# Stage 2: Runtime
FROM python:3.12-slim AS runtime

LABEL maintainer="Jarrad Bermingham <jarrad@steadwise.ai>"
LABEL org.opencontainers.image.source="https://github.com/Jbermingham1/agent-mcp-framework"
LABEL org.opencontainers.image.description="Multi-agent MCP pipeline framework"

WORKDIR /app

# Install the built wheel + runtime dependencies
COPY --from=builder /wheels /wheels
RUN pip install --no-cache-dir /wheels/*.whl && rm -rf /wheels

# Copy entrypoint
COPY docker-entrypoint.py .

# Health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8080/health')" || exit 1

EXPOSE 8080

ENV PORT=8080
ENV HOST=0.0.0.0

CMD ["python", "docker-entrypoint.py"]
