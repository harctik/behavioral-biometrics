# Use Python 3.11 slim image
FROM python:3.11-slim@sha256:4d70b779e5cc401340cd03004bb15cda365d95d12fc45f20f011ba24f46cb6ff

# Set working directory
WORKDIR /app

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV FLASK_ENV=production

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    libffi-dev \
    libssl-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create necessary directories
RUN mkdir -p database models/saved logs

# Create non-root user and set ownership
RUN useradd -r -s /bin/false appuser \
    && chown -R appuser:appuser /app

# Switch to non-root user
USER appuser

# Expose port
EXPOSE 5000

# Healthcheck to detect hung processes
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:5000/healthz || exit 1

# Run Alembic migrations then start the application with gunicorn.
CMD ["sh", "-c", "alembic upgrade head && gunicorn -w 4 -b 0.0.0.0:5000 --timeout 120 --access-logfile - --error-logfile - run:app"]