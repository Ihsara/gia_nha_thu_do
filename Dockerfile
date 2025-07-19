# Multi-stage Docker build for Oikotie Daily Scraper Automation
FROM python:3.11-slim as base

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Install system dependencies with security updates
RUN apt-get update && apt-get install -y --no-install-recommends \
    wget \
    gnupg \
    unzip \
    curl \
    ca-certificates \
    && apt-get upgrade -y \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Install Chrome and ChromeDriver for Selenium
RUN wget -q -O - https://dl-ssl.google.com/linux/linux_signing_key.pub | apt-key add - \
    && echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" >> /etc/apt/sources.list.d/google-chrome.list \
    && apt-get update \
    && apt-get install -y google-chrome-stable \
    && rm -rf /var/lib/apt/lists/*

# Install ChromeDriver
RUN CHROME_DRIVER_VERSION=$(curl -sS chromedriver.storage.googleapis.com/LATEST_RELEASE) \
    && wget -O /tmp/chromedriver.zip http://chromedriver.storage.googleapis.com/$(echo $CHROME_DRIVER_VERSION)/chromedriver_linux64.zip \
    && unzip /tmp/chromedriver.zip chromedriver -d /usr/local/bin/ \
    && rm /tmp/chromedriver.zip \
    && chmod +x /usr/local/bin/chromedriver

# Create application user
RUN groupadd --gid 1000 scraper \
    && useradd --uid 1000 --gid scraper --shell /bin/bash --create-home scraper

# Set working directory
WORKDIR /app

# Install uv for fast Python package management
RUN pip install uv

# Copy dependency files
COPY pyproject.toml uv.lock ./

# Install Python dependencies
RUN uv sync --frozen --no-dev

# Development stage
FROM base as development

# Install development dependencies
RUN uv sync --frozen

# Copy source code
COPY --chown=scraper:scraper . .

# Create necessary directories
RUN mkdir -p /app/data /app/logs /app/output /app/tmp \
    && chown -R scraper:scraper /app

USER scraper

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8080/health || exit 1

# Default command
CMD ["uv", "run", "python", "-m", "oikotie.automation.cli", "run", "--daily"]

# Production stage
FROM base as production

# Copy source code
COPY --chown=scraper:scraper . .

# Create necessary directories with proper permissions
RUN mkdir -p /data /logs /output /shared \
    && chown -R scraper:scraper /data /logs /output /shared /app

# Create volume mount points
VOLUME ["/data", "/logs", "/output", "/shared"]

USER scraper

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8080/health || exit 1

# Expose health check port
EXPOSE 8080

# Set production environment
ENV ENVIRONMENT=production \
    HEADLESS_BROWSER=true \
    HEALTH_CHECK_ENABLED=true \
    DATABASE_PATH=/data/real_estate.duckdb \
    LOG_LEVEL=INFO

# Default command
CMD ["uv", "run", "python", "-m", "oikotie.automation.cli", "run", "--daily"]

# Cluster stage for distributed deployment
FROM production as cluster

# Install Redis client for cluster coordination
RUN uv add redis

# Set cluster environment variables
ENV DEPLOYMENT_TYPE=cluster \
    CLUSTER_COORDINATION_ENABLED=true \
    DATABASE_PATH=/shared/real_estate.duckdb \
    REDIS_URL=redis://redis:6379

# Default command for cluster mode
CMD ["uv", "run", "python", "-m", "oikotie.automation.cli", "run", "--cluster"]