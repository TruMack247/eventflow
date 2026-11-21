# Multi-stage production container
FROM python:3.11-slim

# Set environment
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/src \
    PORT=8080 \
    HOST=0.0.0.0 \
    DATABASE_PATH=event_planner.db

WORKDIR /app

# Copy dependency specifications and readme needed for build
COPY pyproject.toml SPEC.md ./

# Install dependencies (Pydantic, email-validator)
RUN pip install --no-cache-dir "pydantic>=2.0.0" "email-validator>=2.0.0" && pip install --no-cache-dir .

# Copy application source code
COPY src/ ./src/

# Expose default HTTP port
EXPOSE 8080

# Run the standard library web server
CMD ["python", "src/event_planner/web/server.py"]
