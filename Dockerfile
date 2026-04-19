# ─────────────────────────────────────────────────────────────────────────────
# Backend Dockerfile – Multi-stage build
#   Stage 1 (builder): compila dependencias Python
#   Stage 2 (runtime): imagen final limpia
# ─────────────────────────────────────────────────────────────────────────────

# ── Stage 1: Builder ─────────────────────────────────────────────────────────
FROM python:3.11-slim AS builder

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev \
    gcc \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /tmp

COPY requirements.txt .
ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_DEFAULT_TIMEOUT=120

RUN pip install --user --no-cache-dir --retries 10 --timeout 120 -r requirements.txt


# ── Stage 2: Runtime ─────────────────────────────────────────────────────────
FROM python:3.11-slim

# System deps de runtime (sin dev tools)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    curl \
    && rm -rf /var/lib/apt/lists/*

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH=/root/.local/bin:$PATH

WORKDIR /app

# Copiar deps compiladas desde builder
COPY --from=builder /root/.local /root/.local

# Copiar código fuente
COPY . .

# Recolectar archivos estáticos en tiempo de build
# (Usar valores dummy para SECRET_KEY y DB ya que solo se necesitan para collectstatic)
RUN SECRET_KEY=build-placeholder \
    DB_HOST=localhost \
    DB_NAME=placeholder \
    DB_USER=placeholder \
    DB_PASSWORD=placeholder \
    python manage.py collectstatic --noinput --clear 2>/dev/null || true

# Asegurar que los escudos y logos estén disponibles (collectstatic podría no incluirlos)
RUN mkdir -p /app/staticfiles/escudos /app/staticfiles/logos && \
    cp -r /app/static/escudos/* /app/staticfiles/escudos/ 2>/dev/null || true && \
    cp -r /app/static/logos/* /app/staticfiles/logos/ 2>/dev/null || true

# Permisos de ejecución
RUN chmod +x /app/docker-entrypoint.sh

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD curl -f http://localhost:8000/health/ || exit 1

EXPOSE 8000

ENTRYPOINT ["/app/docker-entrypoint.sh"]

