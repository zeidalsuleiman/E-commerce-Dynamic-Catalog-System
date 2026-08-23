FROM python:3.12-slim

# Pillow needs these at build time for image handling (product images feature)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    default-libmysqlclient-dev \
    pkg-config \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Uploaded product images live here (see app/static/uploads/ in the repo,
# gitignored) — declared as a volume mount point in docker-compose.yml
RUN mkdir -p /app/app/static/uploads

EXPOSE 8000

# /health is defined in app/main.py already
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
