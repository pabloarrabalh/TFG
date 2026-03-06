#!/bin/sh
set -e

echo "⏳ Waiting for PostgreSQL…"
until python -c "
import os, psycopg2
psycopg2.connect(
    dbname=os.environ['DB_NAME'],
    user=os.environ['DB_USER'],
    password=os.environ['DB_PASSWORD'],
    host=os.environ['DB_HOST'],
    port=os.environ['DB_PORT'],
)
" 2>/dev/null; do
  sleep 1
done
echo "✅ PostgreSQL ready"

echo "⏳ Running migrations…"
python manage.py migrate --noinput

echo "⏳ Loading initial data (equipos, jugadores, partidos)…"
python manage.py cargar_datos_iniciales --skip-if-exists || echo "⚠️  Could not load initial data"

echo "⏳ Precalculating percentiles…"
python manage.py precalcular_percentiles || echo "⚠️  Could not precalculate percentiles (may not be needed yet)"

echo "⏳ Generating predictions…"
python manage.py generar_predicciones || echo "⚠️  Could not generate predictions (may not be needed yet)"

echo "⏳ Indexing in OpenSearch…"
python manage.py indexar_elasticsearch || echo "⚠️  Could not index in OpenSearch (may not be available yet)"

echo "🚀 Starting Gunicorn…"
exec gunicorn config.wsgi:application \
    --bind 0.0.0.0:8000 \
    --workers 3 \
    --timeout 120 \
    --access-logfile - \
    --error-logfile -

