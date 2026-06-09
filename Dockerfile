FROM python:3.11-slim

WORKDIR /app

# curl for healthcheck + basic tools
RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

# Ensure data dir exists (volume will mount over it on platforms)
RUN mkdir -p /app/data

EXPOSE 8765

HEALTHCHECK --interval=30s --timeout=5s --start-period=60s \
  CMD curl -f http://localhost:8765/api/health || exit 1

CMD ["python", "-m", "app.main"]