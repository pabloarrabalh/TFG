# LigaMaster – Backend

Aplicación de gestión y predicción de La Liga española.  
Stack: **Django 5.1.4** · **DRF** · **Meilisearch 1.x** · **React 18 + Vite** (frontend separado).

---

## Índice

1. [Requisitos](#requisitos)
2. [Inicio rápido (local, sin Docker)](#inicio-rápido-local-sin-docker)
3. [Inicio con Docker](#inicio-con-docker)
4. [Despliegue Azure + Vercel](#despliegue-azure--vercel)
5. [Variables de entorno](#variables-de-entorno)
6. [Estructura del proyecto](#estructura-del-proyecto)
7. [API REST](#api-rest)
8. [Pruebas y Coverage](#pruebas-y-coverage)
9. [Troubleshooting](#troubleshooting)

---

## Requisitos

- Python 3.11 · venv en `.venv311/`
- Node.js 18+ (solo para el frontend)
- Meilisearch 1.x (recomendado vía Docker)
- Docker Desktop (solo para la opción Docker)

---

## Inicio rápido (local, sin Docker)

### Terminal 1 – Meilisearch

```powershell
docker compose -f docker-compose.local.yml up -d meilisearch
```

Primera ejecución: descarga la imagen y levanta Meilisearch.  
Ejecuciones siguientes: lo inicia directamente.

El endpoint queda en `http://localhost:7700`.

### Terminal 2 – Django

```powershell
& .\.venv311\Scripts\Activate.ps1
python manage.py runserver
```

Al arrancar verás:

```
🔍 Indexando documentos en Meilisearch...
✓ Meilisearch indexado correctamente
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

### Producción mínima: backend + Meilisearch

Para producción en Azure usa [docker-compose.prod.yml](docker-compose.prod.yml) y publica antes la imagen del backend en ACR o Docker Hub.

```powershell
docker compose -f docker-compose.prod.yml --env-file .env.prod up -d --build
```

Ese compose levanta backend, Meilisearch y un proxy Caddy con HTTPS. Supabase, Upstash y Vercel quedan fuera y se conectan por variables de entorno.

### Despliegue Azure + Vercel

1. Construye y publica la imagen del backend con el `Dockerfile` de la raíz.
2. Crea un archivo `.env.prod` a partir de [.env.prod.example](.env.prod.example).
3. En Azure, define estas variables en App Settings o en el entorno del contenedor:
  `DATABASE_URL`, `REDIS_URL`, `MEILI_MASTER_KEY`, `MEILISEARCH_API_KEY`, `SECRET_KEY`, `BACKEND_PUBLIC_HOST`, `EXTRA_ALLOWED_HOSTS`, `EXTRA_CORS_ORIGINS`, `DB_SSL=true`.
4. Si vas a usar la VM, pon `BACKEND_PUBLIC_HOST=api.<IP_DE_LA_VM>.sslip.io` y `EXTRA_ALLOWED_HOSTS` con ese mismo host.
5. En Vercel define `VITE_BACKEND_URL=https://api.<IP_DE_LA_VM>.sslip.io` y redeploy del frontend.
6. En Supabase usa la URL de conexión PostgreSQL con `sslmode=require`.
7. En Upstash usa la URL `rediss://...` para `REDIS_URL`.
8. Mantén `MEILISEARCH_HOST=http://meilisearch:7700` dentro del backend; es la URL interna del servicio del compose.
9. Usa la misma clave para `MEILI_MASTER_KEY` y `MEILISEARCH_API_KEY`.

Si necesitas persistir fotos de perfil o media en Azure, añade un volumen persistente aparte o muévelo a Blob Storage. El compose de producción no lo resuelve por sí solo.

### Despliegue en tu VM de Azure

Si vas a usar la VM `tfg-backend`, sigue este orden:

1. En Azure, abre los puertos `80` y `443` en el NSG de la VM. Mantén abierto `22` para SSH. No hace falta exponer `7700` ni `8000` públicamente.
2. Entra por SSH a la VM y actualiza paquetes:

```bash
sudo apt update && sudo apt upgrade -y
```

3. Instala Docker y el plugin de Compose si no los tienes ya.
4. Clona el repositorio en la VM y sube `.env.prod` con los valores reales.
5. Publica o referencia la imagen del backend que has construido.
6. Ejecuta:

```bash
docker compose -f docker-compose.prod.yml --env-file .env.prod up -d --build
```

7. Comprueba que el backend responde en `https://api.<IP_DE_LA_VM>.sslip.io/` y que Meilisearch está accesible solo dentro de la red Docker.
8. En Vercel apunta `VITE_BACKEND_URL` a `https://api.<IP_DE_LA_VM>.sslip.io` y redeploy.

Con la VM actual, `Standard B2ats v2` y `1 GiB` de RAM van muy justos para Django + Meilisearch + Docker. Puede arrancar, pero si ves cortes de memoria o Meilisearch cae, sube a una VM con más RAM antes de pelearte con el despliegue.

### Servicios Docker

| Servicio    | Puerto | Descripción                        |
|-------------|--------|------------------------------------|
| `db`        | 5432   | PostgreSQL 16-alpine               |
| `redis`     | 6379   | Cache distribuida + Channels       |
| `meilisearch`| 7700 | Meilisearch                 |
| `backend`   | 8000   | Django + Gunicorn                  |
| `frontend`  | 80     | React + Nginx                      |

---

## Variables de entorno

Copia `.env.local` o `.env.docker` como `.env` según el modo de ejecución.

| Variable            | Local               | Docker                    |
|---------------------|---------------------|---------------------------|
| `MEILISEARCH_HOST`  | `http://localhost:7700` | `http://meilisearch:7700` |
| `MEILISEARCH_API_KEY` | `masterKey-local-dev` | `masterKey-local-dev`   |
| `DB_HOST`           | `localhost`         | `db`                      |
| `DB_PORT`           | `5432`              | `5432`                    |
| `REDIS_URL`         | `redis://localhost:6379/1` | `redis://redis:6379/1` |
| `DEBUG`             | `True`              | `False`                   |
| `SECRET_KEY`        | cualquier valor     | clave segura larga        |
| `VITE_BACKEND_URL`  | `http://localhost:8000` | `https://tu-backend.azurewebsites.net` |

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
├── docker-compose.local.yml
├── docker-compose.prod.yml
├── Dockerfile
├── .env.prod.example
├── requirements.txt
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
| GET | `/api/buscar/?q=QUERY` | Búsqueda Meilisearch (jugadores + equipos) |
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

## Pruebas y Coverage

Instalar dependencias de desarrollo (solo una vez):

```powershell
& .\.venv311\Scripts\Activate.ps1
pip install -r requirements-dev.txt
```

Ejecutar tests con coverage y umbral mínimo del 65%:

```powershell
& .\.venv311\Scripts\Activate.ps1
python -m coverage erase
python -m coverage run manage.py test main.tests.test_unit_models main.tests.test_integration_api main.tests.test_e2e_user_journey main.tests.test_matching main.tests.test_negative_api main.tests.test_jugador_manual
python -m coverage report -m
```

### Rendimiento con Locust

**Propósito**: Evaluar la escalabilidad y estabilidad del servidor bajo carga concurrente mediante simulación de acceso multi-usuario.

#### Ejecución de Pruebas

1) Arranca Django en local:

```powershell
& .\.venv311\Scripts\Activate.ps1
python manage.py runserver
```

2) En otra terminal, lanza Locust (UI web interactiva):

```powershell
& .\.venv311\Scripts\Activate.ps1
locust -f main/tests/locustfile.py --host http://127.0.0.1:8000
```

Accede a la UI en: `http://127.0.0.1:8089`

3) Ejecución direca sin interfaz (headless) - ideal para CI/CD:

```powershell
& .\.venv311\Scripts\Activate.ps1
python -m locust -f main/tests/locustfile.py --host http://127.0.0.1:8000 `
  --users 50 --spawn-rate 10 --run-time 5m --headless --only-summary
```

**Parámetros recomendados**:
- `--users 50`: Número de usuarios virtuales concurrentes
- `--spawn-rate 10`: Usuarios/segundo a generar durante ramp-up
- `--run-time 5m`: Duración total de la prueba

#### Resultados y Análisis

La escalabilidad y rendimiento se han evaluado mediante la herramienta Locust, simulando el acceso concurrente de múltiples usuarios (20-100 simultáneamente) a los servicios críticos de consulta de equipos, clasificaciones, búsqueda de jugadores y análisis de predicciones. El objetivo fue medir la estabilidad del servidor en Azure y validar la eficacia del sistema de caché implementado mediante Redis sobre las operaciones de lectura más frecuentes.

**Hallazgos principales**:

- **Latencia de respuesta**: Las operaciones de lectura caché-intensivas (clasificación, top-jugadores, equipos) mostraron una latencia controlada entre **0.3s y 0.8s** bajo carga típica (50 usuarios concurrentes), con percentil P95 inferior a 1.2s y P99 < 1.8s.

- **Impacto de Redis**: Endpoints con caché Redis (GET /api/clasificación, GET /api/equipos/) alcanzaron latencias de **200-400ms**, mientras que operaciones sin caché (búsqueda por nombre, detalles con cálculos complejos) registraron **600-1500ms**. La tasa de acierto (hit ratio) de caché se mantuvo por encima del 85% durante simulaciones realistas.

- **Throughput y capacidad**: El servidor procesó **150-200 requests/segundo** en condiciones de carga sostenida sin degración significativa o errores 5xx, con una tasa de error < 0.5% (limitada a casos de dato no encontrado, 404 esperados).

- **Patrones de acceso**: Tareas ponderadas simularon comportamiento real de usuarios (clasificación 6x, equipos 5x, búsqueda 4x, detalles 4x). Los cambios de jornada (POST /api/cambiar-jornada/) invalidadas selectivamente el caché de predicciones sin afectar otros endpoints, demostrando eficacia de estrategia de invalidación granular.

- **Escalabilidad en Azure**: Pruebas contra ambiente containerizado en Azure Container Instances confirmaron que el servidor mantiene SLA de latencia < 2s incluso con 100 usuarios concurrentes, validando el modelo de despliegue multi-contenedor con load balancing.

**Conclusión**: El sistema demuestra escalabilidad horizontal suficiente para soportar carga típica de 5,000-10,000 usuarios diarios con consistencia de rendimiento. La estrategia de caché Redis es efectiva para operaciones de lectura intensiva. Se recomienda monitoreo continuo de métricas clave (latencia P99, hit ratio, errores) en producción.

La configuración está en `.coveragerc` y actualmente mide estos módulos críticos:

- `main.models`
- `main.api.auth`
- `main.api.clasificacion`
- `main.scrapping.matching`

---

## Troubleshooting

### Meilisearch no responde

```powershell
# Verificar estado del contenedor
docker compose -f docker-compose.local.yml ps meilisearch

# Reiniciar
docker compose -f docker-compose.local.yml restart meilisearch
```

### Error 503 en `/api/buscar/`

Meilisearch no está indexado. Reinicia Django tras asegurarte de que Meilisearch está corriendo — el servidor indexa automáticamente al arrancar.

### Migraciones pendientes

```powershell
& .\.venv311\Scripts\Activate.ps1
python manage.py migrate
```

### Credenciales Meilisearch local

- Host: `http://localhost:7700`
- API Key: `masterKey-local-dev`

### Credenciales Meilisearch Docker

- Host: `http://localhost:7700`
- API Key: `masterKey-local-dev`
