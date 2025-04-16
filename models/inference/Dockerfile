FROM python:3.9-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends curl && \
    rm -rf /var/lib/apt/lists/* && \
    adduser --disabled-password --gecos "" appuser
USER appuser

# Set Python settings for production
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Copy requirements first for better caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt && pip install hf_xet

# Copy the application code
COPY app.py .

# Expose the application and metrics ports
EXPOSE 8080 8000

HEALTHCHECK --interval=30s --timeout=3s --retries=3 \
    CMD ["sh", "-c", "curl -f http://localhost:8080/health || exit 1"]

# Run the application
CMD ["python", "app.py"] 