#!/bin/bash
# ──────────────────────────────────────────────────────────────────────────────
# Docker entrypoint unificado (local / Render / Azure)
#
# Lógica de arranque:
#   1. Esperar PostgreSQL y OpenSearch
#   2. Ejecutar migraciones siempre (idempotente)
#   3. Comprobar si la BD ya está poblada:
#        - ≥500 jugadores  Y  ≥100 predicciones  → SKIP población (BD persistente)
#        - Menos datos     → cargar todo (primera vez o BD nueva)
#   4. Lanzar background worker de predicciones
#   5. Arrancar Daphne
# ──────────────────────────────────────────────────────────────────────────────

set -e

cd /app

# ── 1. Esperar PostgreSQL ─────────────────────────────────────────────────────
echo "[WAIT] Esperando PostgreSQL..."
MAX_TRIES=30
for i in $(seq 1 $MAX_TRIES); do
    python -c "
import os, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()
from django.db import connection
connection.ensure_connection()
" 2>/dev/null && echo "[WAIT] PostgreSQL listo." && break
    echo "  Retry $i/$MAX_TRIES..."
    sleep 3
    if [ "$i" -eq "$MAX_TRIES" ]; then
        echo "[ERROR] PostgreSQL no responde tras $MAX_TRIES intentos. Abortando."
        exit 1
    fi
done

# ── 2. Migraciones (siempre, idempotente) ─────────────────────────────────────
echo "[MIGRATIONS] Ejecutando migraciones..."
python manage.py migrate --noinput

# ── 2.5. Recolectar archivos estáticos ────────────────────────────────────────
echo "[STATIC] Recolectando archivos estáticos..."
python manage.py collectstatic --noinput --clear 2>&1 | tail -n 5

# ── 3. Detectar si la BD ya tiene suficientes datos ──────────────────────────
echo "[CHECK] Comprobando estado de la base de datos..."
DB_STATUS=$(python -c "
import os, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()
from main.models import Jugador, PrediccionJugador
jugadores = Jugador.objects.count()
predicciones = PrediccionJugador.objects.count()
print(f'{jugadores},{predicciones}')
" 2>/dev/null || echo "0,0")

JUGADORES=$(echo "$DB_STATUS" | cut -d',' -f1)
PREDICCIONES=$(echo "$DB_STATUS" | cut -d',' -f2)

echo "  Jugadores en BD: ${JUGADORES} (mínimo requerido: 500)"
echo "  Predicciones en BD: ${PREDICCIONES} (mínimo requerido: 100)"

if [ "${JUGADORES:-0}" -ge 500 ] && [ "${PREDICCIONES:-0}" -ge 100 ]; then
    echo "[OK] BD ya está poblada - saltando carga inicial (BD persistente detectada)"
    NEEDS_INIT=false
else
    echo "[INIT] BD incompleta - iniciando carga de datos (primera vez o BD nueva)..."
    echo "       Esto puede tardar 10-20 minutos. Tiempo estimado por paso:"
    echo "       - Carga de datos CSV:     ~2-3 min"
    echo "       - Percentiles:            ~1 min"
    echo "       - Medias históricas:      ~1 min"
    echo "       - Predicciones ML:        ~5-10 min"
    echo "       - Indexado OpenSearch:    ~1 min"
    NEEDS_INIT=true
fi

if [ "$NEEDS_INIT" = "true" ]; then
    _TOTAL_START=$(date +%s)

    echo "[STEP 1/5] Cargando datos iniciales (CSV, partidos, jugadores)..."
    _T=$(date +%s)
    python manage.py cargar_datos_iniciales --verbosity=1 2>&1 || {
        echo "[WARN] cargar_datos_iniciales terminó con errores (puede ser normal)"
    }
    echo "  Tiempo carga datos: $(($(date +%s) - _T))s"

    echo "[STEP 2/5] Calculando posiciones y percentiles..."
    _T=$(date +%s)
    python manage.py precalcular_percentiles --verbosity=0 2>&1 || true
    echo "  Tiempo percentiles: $(($(date +%s) - _T))s"

    echo "[STEP 3/5] Generando medias históricas..."
    _T=$(date +%s)
    python manage.py generar_medias_historicas --workers 16 --verbosity=0 2>&1 || true
    echo "  Tiempo medias: $(($(date +%s) - _T))s"

    echo "[STEP 4/5] Generando predicciones ML para jugadores activos (60+ min, jornadas 1-38)..."
    _T=$(date +%s)
    python manage.py generar_predicciones --all-jornadas --init-active-only --workers 32 --batch 300 --force --verbosity=0 2>&1 || true
    echo "  Tiempo predicciones: $(($(date +%s) - _T))s"

    echo "[STEP 5/5] Indexando en OpenSearch..."
    _T=$(date +%s)
    python manage.py indexar_opensearch --verbosity=0 2>&1 || true
    echo "  Tiempo indexado: $(($(date +%s) - _T))s"

    echo "============================================================"
    echo "[OK] Carga inicial completada en $(($(date +%s) - _TOTAL_START))s"
    echo "============================================================"
else
    # BD ya poblada: solo re-indexar OpenSearch si está vacío
    echo "[CHECK] Verificando índice OpenSearch..."
    python -c "
import os, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()
from main.opensearch_docs import OPENSEARCH_AVAILABLE, opensearch_client
if not OPENSEARCH_AVAILABLE:
    print('OPENSEARCH_NOT_AVAILABLE')
    exit()
try:
    r = opensearch_client.count(index='jugadores')
    if r.get('count', 0) < 100:
        print('NEEDS_INDEX')
    else:
        print('INDEX_OK')
except Exception:
    print('NEEDS_INDEX')
" 2>/dev/null > /tmp/os_check.txt || echo "NEEDS_INDEX" > /tmp/os_check.txt

    OS_STATUS=$(cat /tmp/os_check.txt)
    if [ "$OS_STATUS" = "NEEDS_INDEX" ]; then
        echo "[OPENSEARCH] Índice vacío - re-indexando..."
        python manage.py indexar_opensearch --verbosity=0 2>&1 || true
    else
        echo "[OPENSEARCH] Índice OK (${OS_STATUS})"
    fi
fi

# ── 4. Lanzar background worker de predicciones pendientes ────────────────────
echo "[BACKGROUND] Iniciando generador de predicciones en background..."
python manage.py generar_predicciones_background --batch 50 --wait 2 --tempo 25_26 --verbosity=0 2>&1 &
BG_PID=$!
echo "  PID background: $BG_PID"

# ── 5. Arrancar servidor Django (ASGI) ────────────────────────────────────────
echo "[LAUNCH] Iniciando Daphne en 0.0.0.0:8000..."
exec daphne -b 0.0.0.0 -p 8000 config.asgi:application
