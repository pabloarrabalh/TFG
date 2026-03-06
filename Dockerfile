# ── Backend Dockerfile ────────────────────────────────────────────────────────
FROM python:3.11-slim

# System deps needed by psycopg2 and Pillow
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev \
    gcc \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python deps
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt gunicorn

# Copy source
COPY . .

# Collect static files at build time (needs a dummy DB env so Django doesn't crash)
RUN DB_HOST=localhost python manage.py collectstatic --noinput || true

EXPOSE 8000

COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
