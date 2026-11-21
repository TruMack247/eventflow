# Multi-stage production container
FROM python:3.11-slim

# Set environment
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/src \
    PORT=8080 \
    HOST=0.0.0.0 \
    DATABASE_PATH=/data/event_planner.db

WORKDIR /app

# Copy dependency specifications
COPY pyproject.toml .

# Install dependencies (Pydantic, email-validator)
RUN pip install --no-cache-dir .

# Copy application source code
COPY src/ ./src/

# Create mount directory for persistent SQLite database
RUN mkdir -p /data

# Expose default HTTP port
EXPOSE 8080

# Run the standard library web server
CMD ["python", "src/event_planner/web/server.py"]
