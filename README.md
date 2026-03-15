# LigaMaster – Backend

Aplicación de gestión y predicción de La Liga española.  
Stack: **Django 5.1.4** · **DRF** · **OpenSearch 3.5.0** · **React 18 + Vite** (frontend separado).

---

## Índice

1. [Requisitos](#requisitos)
2. [Inicio rápido (local, sin Docker)](#inicio-rápido-local-sin-docker)
3. [Inicio con Docker](#inicio-con-docker)
4. [Variables de entorno](#variables-de-entorno)
5. [Estructura del proyecto](#estructura-del-proyecto)
6. [API REST](#api-rest)
7. [Troubleshooting](#troubleshooting)

---

## Requisitos

- Python 3.11 · venv en `.venv311/`
- Node.js 18+ (solo para el frontend)
- OpenSearch 3.5.0 (descargado automáticamente por `start-opensearch-local.ps1`)
- Docker Desktop (solo para la opción Docker)

---

## Inicio rápido (local, sin Docker)

### Terminal 1 – OpenSearch

```powershell
.\start-opensearch-local.ps1
```

Primera ejecución: descarga OpenSearch (~700 MB) y lo inicia.  
Ejecuciones siguientes: lo inicia directamente.

Deja esta terminal abierta — el endpoint queda en `http://localhost:9200`.

### Terminal 2 – Django

```powershell
& .\.venv311\Scripts\Activate.ps1
python manage.py runserver
```

Al arrancar verás:

```
🔍 Indexando documentos en OpenSearch...
✓ OpenSearch indexado correctamente
Starting development server at http://127.0.0.1:8000/
```

### Terminal 3 – Frontend (React)

```powershell
cd frontend-web
npm install   # solo la primera vez
npm run dev
```

Acceso: **http://localhost:5173**

---

## Inicio con Docker

```powershell
docker compose up --build   # primera vez
docker compose up           # arranques posteriores
```

En otra terminal:

```powershell
cd frontend-web
npm run dev
```

Acceso: **http://localhost:8000** (Django + Nginx)

### Servicios Docker

| Servicio    | Puerto | Descripción                        |
|-------------|--------|------------------------------------|
| `db`        | 5432   | PostgreSQL 16-alpine               |
| `opensearch`| 9200   | OpenSearch                  |
| `backend`   | 8000   | Django + Gunicorn                  |
| `frontend`  | 80     | React + Nginx                      |

---

## Variables de entorno

Copia `.env.local` o `.env.docker` como `.env` según el modo de ejecución.

| Variable            | Local               | Docker                    |
|---------------------|---------------------|---------------------------|
| `OPENSEARCH_HOST`   | `localhost:9200`    | `opensearch:9200`         |
| `OPENSEARCH_USER`   | `admin`             | `admin`                   |
| `OPENSEARCH_PASSWORD`| `admin`            | `Admin_Password1!`        |
| `DB_HOST`           | `localhost`         | `db`                      |
| `DB_PORT`           | `5432`              | `5432`                    |
| `DEBUG`             | `True`              | `False`                   |
| `SECRET_KEY`        | cualquier valor     | clave segura larga        |

Generar una `SECRET_KEY` nueva:

```powershell
& .\.venv311\Scripts\python.exe -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

---

## Estructura del proyecto

```
TFG/
├── config/                 # Settings, urls raíz, wsgi/asgi
├── main/
│   ├── api/                # DRF APIViews (REST API v1)
│   │   ├── auth.py         # /api/me/, /api/auth/…
│   │   ├── buscar.py       # /api/buscar/, /api/radar/…
│   │   ├── clasificacion.py
│   │   ├── consejero.py    # Consejero ML (SHAP)
│   │   ├── equipo.py
│   │   ├── estadisticas.py
│   │   ├── favoritos.py
│   │   ├── jugador.py
│   │   ├── menu.py
│   │   ├── notificaciones.py
│   │   ├── perfil.py       # /api/perfil/…
│   │   ├── plantilla.py
│   │   └── …
│   ├── views/              # Vistas de plantilla Django (HTML)
│   ├── models.py
│   ├── serializers.py
│   ├── drf_views.py        # REST API v2
│   └── urls.py
├── frontend-web/           # App React (no tocar desde el backend)
├── static/
│   ├── escudos/            # PNGs de los escudos de equipos (150–200 px, fondo transparente)
│   └── logos/
├── media/
│   └── profile_pics/       # Fotos de perfil de usuario (carpeta plana)
├── docker-compose.yml
├── Dockerfile
├── requirements.txt
├── start-opensearch-local.ps1   # Único script PS1: inicia OpenSearch localmente
└── docs/
    └── TECHNICAL_DOCUMENTATION.md   # Documentación técnica detallada
```

---

## API REST

### v1 (DRF) – endpoints principales

| Método | Ruta | Descripción |
|--------|------|-------------|
| GET | `/api/me/` | Usuario actual + CSRF cookie |
| POST | `/api/auth/login/` | Login |
| POST | `/api/auth/logout/` | Logout |
| POST | `/api/auth/register/` | Registro |
| GET | `/api/menu/` | Datos del menú principal |
| GET | `/api/clasificacion/` | Clasificación de La Liga |
| GET | `/api/equipos/` | Lista de equipos |
| GET | `/api/equipo/<nombre>/` | Detalle de equipo |
| GET | `/api/jugador/<id>/` | Detalle de jugador |
| GET | `/api/radar/<id>/<temporada>/` | Datos radar chart (percentiles) |
| GET | `/api/buscar/?q=QUERY` | Búsqueda OpenSearch (jugadores + equipos) |
| GET | `/api/perfil/` | Perfil del usuario autenticado |
| PATCH | `/api/perfil/update/` | Actualizar datos del perfil |
| PATCH | `/api/perfil/status/` | Cambiar estado (active/away/dnd) |
| POST | `/api/perfil/foto/` | Subir foto de perfil |
| PATCH | `/api/perfil/preferencias-notificaciones/` | Preferencias de notificaciones |
| POST | `/api/perfil/cambiar-jornada/` | Cambiar jornada activa |
| GET/POST | `/api/favoritos/` | Equipos favoritos |
| POST | `/api/favoritos/toggle/` | Toggle equipo favorito |
| GET | `/api/consejero/` | Consejero ML (predicciones + SHAP) |
| GET | `/api/estadisticas/` | Estadísticas de jugadores |

### v2 (DRF) – endpoints extendidos

Prefijo `/api/v2/`. Ver `main/drf_views.py` para la lista completa.

---

## Troubleshooting

### OpenSearch no responde

```powershell
# Verificar proceso Java
Get-Process java

# Reiniciar
.\start-opensearch-local.ps1
```

### Error 503 en `/api/buscar/`

OpenSearch no está indexado. Reinicia Django tras asegurarte de que OpenSearch está corriendo — el servidor indexa automáticamente al arrancar.

### Migraciones pendientes

```powershell
& .\.venv311\Scripts\Activate.ps1
python manage.py migrate
```

### Credenciales OpenSearch local

- Host: `http://localhost:9200`
- Usuario: `admin`
- Contraseña: `admin`

### Credenciales OpenSearch Docker

- Host: `http://localhost:9200`
- Usuario: `admin`
- Contraseña: `Admin_Password1!`
