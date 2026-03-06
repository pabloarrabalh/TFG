cd C:\Users\pablo\Desktop\TFG
ren .env.docker .env# 🚀 Guía de Dockerización y Cambios

## 📋 Cambios Realizados

### 1. **Reorganización de `main/`**
- `views_*.py` (8 ficheros) → `main/views/` subpackage
- `api_*.py` (10 ficheros) → `main/api/` subpackage
- `main/views.py` → ahora es `main/views/__init__.py` (façade)
- `main/api_views.py` → ahora es un proxy de 69 líneas que re-exporta desde `main/api/`

**Ventaja:** estructura limpia sin 400 módulos sueltos en `main/`

### 2. **Base de Datos: SQLite → PostgreSQL**
```python
# Antes:
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}

# Ahora:
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.environ.get('DB_NAME', 'laliga'),
        'USER': os.environ.get('DB_USER', 'laliga_user'),
        'PASSWORD': os.environ.get('DB_PASSWORD', 'laliga_pass'),
        'HOST': os.environ.get('DB_HOST', 'localhost'),
        'PORT': os.environ.get('DB_PORT', '5432'),
        'OPTIONS': {'client_encoding': 'UTF8'},
    }
}
```

**Cambios en requirements.txt:**
- ✅ Añadido: `psycopg2-binary==2.9.10`

**Nota:** No hay SQL crudo en el código, todo es ORM Django → cambio transparente.

### 3. **Archivos Docker Creados**

| Fichero | Propósito |
|---------|-----------|
| `Dockerfile` | Backend: Python 3.11 + Gunicorn |
| `entrypoint.sh` | Waits for PostgreSQL → migrations → starts Gunicorn |
| `frontend-web/Dockerfile` | Frontend: Node build + Nginx |
| `frontend-web/nginx.conf` | Nginx config (proxies `/api/*` a Django) |
| `docker-compose.yml` | Orquestación: db + opensearch + backend + frontend |
| `.env.docker` | Variables de entorno (template) |

### 4. **Servicios Docker** 🐳

```yaml
db           # PostgreSQL 16-alpine
opensearch   # OpenSearch 2.11.0 (búsqueda)
backend      # Django + Gunicorn (Puerto 8000)
frontend     # React + Nginx (Puerto 80)
```

---

## 🔧 Cómo Arrancar en Docker

### Paso 1: Preparar `.env.docker`

```bash
cd c:\Users\pablo\Desktop\TFG
notepad .env.docker
```

Edita estos valores (el resto deja como está):
```env
SECRET_KEY=tu-clave-secreta-muy-larga-aqui-12345
DEBUG=False
```

**⚠️ IMPORTANTE:** Genera una SECRET_KEY real:
```bash
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

### Paso 2: Construir e Iniciar

**Primera vez (construir todo):**
```bash
cd c:\Users\pablo\Desktop\TFG
docker compose up --build
```

**Arranques posteriores:**
```bash
docker compose up
```

### Paso 3: Verifica que esté todo correcto

Espera a que veas esto:
```
backend    | 🚀 Starting Gunicorn…
backend    | [XXXX] [INFO] Listening at: http://0.0.0.0:8000 (XXXX)
```

---

## 🌐 Accesos Cuando Está Corriendo

| URL | Qué es |
|-----|--------|
| `http://localhost` | React frontend |
| `http://localhost:8000` | Django sin proxy (debug) |
| `http://localhost:8000/admin` | Admin de Django |
| `http://localhost:9200` | OpenSearch (búsqueda) |

---

## 🛑 Parar Todo

```bash
# Parar contenedores (mantiene datos)
docker compose down

# Parar contenedores + borrar datos (limpia todo)
docker compose down -v
```

---

## 📊 Base de Datos en Docker

**Ubicación de datos:** Docker volume `postgres_data`

**Acceder a la BD desde fuera del contenedor:**
```bash
# Descubre el nombre del volumen exacto
docker volume ls

# O usa Python directamente:
python
>>> import psycopg2
>>> conn = psycopg2.connect(
...     dbname="laliga",
...     user="laliga_user",
...     password="laliga_pass",
...     host="localhost",
...     port="5432"
... )
```

**Respaldar la BD:**
```bash
docker exec tfg-db-1 pg_dump -U laliga_user laliga > backup.sql
```

**Restaurar:**
```bash
docker exec -i tfg-db-1 psql -U laliga_user laliga < backup.sql
```

---

## 🐞 Troubleshooting

### *"ConnectionRefusedError" en backend*
→ PostgreSQL no está listo → espera 10-15 segundos

### *"Certificate verification failed" en OpenSearch*
→ Normal en desarrollo. No afecta la app. Ignore en logs.

### *Frontend no carga*
→ Espera a que Nginx esté listo (30 segundos)
→ Limpia caché del navegador (Ctrl+Shift+Del)

### *Cambios en código no se reflejan*
```bash
docker compose restart backend
```

### *"Port 80 already in use"*
```bash
docker compose down  # antes de volver a arrancar
# O cambia el puerto en docker-compose.yml:
# ports:
#   - "8080:80"  # ahora en localhost:8080
```

---

## ✅ Checklist Antes de Producción

- [ ] Editar `.env.docker` con valores reales
- [ ] Cambiar `DEBUG=False` en `.env.docker`
- [ ] SECRET_KEY es única y segura
- [ ] Validar que `docker compose up --build` no da errores
- [ ] Comprobar que datos se cargan en PostgreSQL
- [ ] Frontend carga en `http://localhost`
- [ ] API responde en `http://localhost/api/me/`

---

## 📝 Resumen Rápido

```bash
# 1. Edita .env.docker
notepad .env.docker

# 2. Construir y arrancar
docker compose up --build

# 3. Ingresa a http://localhost
# ✅ Listo
```

---

## 🔄 Migrations & Datos

Las migraciones se ejecutan automáticamente en `entrypoint.sh` del backend:
```bash
python manage.py migrate --noinput
```

**Si necesitas limpiar y empezar desde cero:**
```bash
docker compose down -v
docker compose up --build
```

---

## 📞 Notas Finales

- **PostgreSQL:** Los datos persisten en el volumen `postgres_data`
- **OpenSearch:** Datos de búsqueda en volumen `opensearch_data`
- **Static files:** `main/staticfiles/` (generados automáticamente)
- **Media:** `main/media/` dentro del volumen `media_data`

**Toda la infraestructura está lista. Solo arrancar Docker y funciona. 🚀**
