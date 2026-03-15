# Guía de Despliegue — LigaMaster

Esta guía cubre los tres entornos de la aplicación:

| Entorno | Dónde | Archivo env | Compose |
|---------|-------|-------------|---------|
| Local (sin Docker) | `python manage.py runserver` | `.env.local` | — |
| Local (con Docker) | Docker Desktop | `.env.docker` → `.env` | `docker-compose.yml` |
| Pre-producción | Render.com | `.env.render` (dashboard) | `docker-compose.render.yml` |
| Producción | Azure Container Apps | `.env.azure` (az CLI) | `docker-compose.azure.yml` |

---

## 1. Desarrollo local (sin Docker)

### Requisitos previos
- Python 3.11+, Node 20+
- PostgreSQL 16 corriendo en `localhost:5432`
- OpenSearch 2.11.0 corriendo en `localhost:9200`

### Pasos

```bash
# 1. Entorno virtual
python -m venv .venv311
.venv311\Scripts\activate          # Windows
# source .venv311/bin/activate     # Linux/Mac

# 2. Dependencias Python
pip install -r requirements.txt

# 3. Variables de entorno
#    Revisa .env.local y ajusta DB_PASSWORD etc.
#    En Linux: export $(grep -v '#' .env.local | xargs)
#    En Windows PowerShell:
Get-Content .env.local | Where-Object { $_ -notmatch '^#' -and $_ -ne '' } |
    ForEach-Object { $kv = $_ -split '=',2; [System.Environment]::SetEnvironmentVariable($kv[0], $kv[1]) }

# 4. Crear base de datos PostgreSQL
psql -U postgres -c "CREATE DATABASE laliga;"
psql -U postgres -c "CREATE USER laliga_user WITH PASSWORD 'tu_password';"
psql -U postgres -c "GRANT ALL PRIVILEGES ON DATABASE laliga TO laliga_user;"

# 5. Migraciones y datos iniciales
python manage.py migrate
python manage.py runserver

# 6. Frontend (en otra terminal)
cd frontend-web
npm install
npm run dev           # http://localhost:5173
```

---

## 2. Desarrollo local con Docker

### Requisitos previos
- Docker Desktop corriendo

### Pasos

```bash
# 1. Copiar template de entorno
copy .env.docker .env      # Windows
# cp .env.docker .env      # Linux/Mac
# Edita .env y rellena DB_PASSWORD, SECRET_KEY, API_FOOTBALL_KEY

# 2. Levantar todos los servicios (primera vez tarda ~5 min por la carga de datos)
docker compose up --build

# Servicios:
#   Backend  → http://localhost:8000
#   Frontend → http://localhost:3000
#   OpenSearch Dashboard → http://localhost:5601

# 3. Parar sin borrar volúmenes (datos persistentes)
docker compose stop

# 4. Parar Y borrar volúmenes (datos nuevos en próximo up)
docker compose down -v
```

### Lógica de inicio automático

El `docker-entrypoint.sh` comprueba si la BD ya tiene datos antes de repoblar:

- **≥500 jugadores Y ≥100 predicciones** → salta toda la inicialización (inicio rápido ~30s)
- **Menos datos** → ejecuta el pipeline completo: `cargar_datos` → `percentiles` → `medias` → `predicciones` → index OpenSearch (~10-20 min en primer arranque)

OpenSearch se re-indexa si el índice tiene <100 documentos, aunque la BD ya esté poblada.

---

## 3. Pre-producción en Render.com

### Arquitectura
- **Backend** — Render Web Service (Docker)
- **Frontend** — Render Web Service (Docker)  
- **PostgreSQL** — Render PostgreSQL (managed, 1 GB plan free)
- **OpenSearch** — Bonsai (plan free, 125 MB) o Aiven

### Paso a paso

#### 3.1 Crear base de datos PostgreSQL en Render

1. Render dashboard → **New +** → **PostgreSQL**
2. Nombre: `ligamaster-db`
3. Plan: Free (o Starter para persistencia >90 días)
4. Anotar la **Internal Database URL** (formato `postgres://...`)

#### 3.2 Crear OpenSearch (Bonsai)

1. Ir a [app.bonsai.io](https://app.bonsai.io) → crear cuenta
2. Crear cluster → anotar `Host`, `User`, `Password`
3. El host tiene formato: `xxxxx.bonsaisearch.net:443`

#### 3.3 Crear Web Service — Backend

1. Render dashboard → **New +** → **Web Service**
2. Conectar repositorio GitHub
3. **Runtime**: Docker
4. **Dockerfile path**: `./Dockerfile`
5. **Environment variables** (añadir una a una):

```
SECRET_KEY            = <genera con: python -c "import secrets; print(secrets.token_hex(50))">
DEBUG                 = False
DJANGO_SETTINGS_MODULE = config.settings
DATABASE_URL          = <pega la Internal Database URL de Render>
OPENSEARCH_HOST       = <host:puerto de Bonsai>
OPENSEARCH_USER       = <usuario Bonsai>
OPENSEARCH_PASSWORD   = <password Bonsai>
OPENSEARCH_USE_SSL    = True
EXTRA_ALLOWED_HOSTS   = tu-app.onrender.com
EXTRA_CORS_ORIGINS    = https://tu-frontend.onrender.com
API_FOOTBALL_KEY      = <tu clave>
```

> **Tip:** Si enlazas el servicio PostgreSQL de Render al Web Service, Render inyecta `DATABASE_URL` automáticamente y no necesitas copiarla a mano.

6. **Health Check Path**: `/health/`
7. Deploy → esperar el primer arranque (~10-20 min mientras puebla la BD)

#### 3.4 Crear Web Service — Frontend

1. **New +** → **Web Service** → Docker
2. **Dockerfile path**: `./frontend-web/Dockerfile`
3. **Build command** (override): dejar vacío (el Dockerfile lo hace todo)
4. **Environment variables**:

```
VITE_API_URL = https://tu-backend.onrender.com
```

5. Deploy

#### 3.5 Verificar

```bash
curl https://tu-backend.onrender.com/health/
# → {"status": "ok"}

curl https://tu-backend.onrender.com/api/jugadores/?page=1
```

---

## 4. Producción en Azure Container Apps

### Arquitectura
- **Azure Container Registry (ACR)** — almacena las imágenes Docker
- **Azure Container Apps** — ejecuta backend y frontend sin gestionar VMs
- **Azure Database for PostgreSQL Flexible Server** — BD persistente gestionada
- **Aiven Managed OpenSearch** — OpenSearch como servicio

### Requisitos
- [Azure CLI](https://learn.microsoft.com/cli/azure/install-azure-cli) instalado
- Cuenta Azure con suscripción activa
- Docker Desktop corriendo

---

#### 4.1 Preparar Azure CLI

```bash
az login
az account set --subscription "<nombre o ID de tu suscripción>"

# Variables de conveniencia
$RESOURCE_GROUP = "ligamaster-rg"
$LOCATION       = "westeurope"
$ACR_NAME       = "ligamasteracr"          # debe ser único globalmente
$ENV_NAME       = "ligamaster-env"
```

#### 4.2 Crear grupo de recursos y ACR

```bash
az group create --name $RESOURCE_GROUP --location $LOCATION

az acr create --resource-group $RESOURCE_GROUP `
    --name $ACR_NAME --sku Basic --admin-enabled true

# Obtener credenciales ACR
$ACR_PASSWORD = $(az acr credential show --name $ACR_NAME --query passwords[0].value -o tsv)
```

#### 4.3 Construir y subir imágenes a ACR

```bash
# Login en ACR
az acr login --name $ACR_NAME

# Build y push — backend
docker build -t "$ACR_NAME.azurecr.io/ligamaster-backend:latest" .
docker push "$ACR_NAME.azurecr.io/ligamaster-backend:latest"

# Build y push — frontend (con URL del backend)
docker build `
    --build-arg VITE_API_URL="https://ligamaster-backend.<unique>.westeurope.azurecontainerapps.io" `
    -t "$ACR_NAME.azurecr.io/ligamaster-frontend:latest" `
    ./frontend-web
docker push "$ACR_NAME.azurecr.io/ligamaster-frontend:latest"
```

> **Nota:** La URL del backend la sabes después del paso 4.6. En el primer deploy usa un placeholder y actualiza la imagen del frontend después.

#### 4.4 Crear Azure Database for PostgreSQL Flexible Server

```bash
az postgres flexible-server create `
    --resource-group $RESOURCE_GROUP `
    --name ligamaster-db `
    --location $LOCATION `
    --admin-user laliga_admin `
    --admin-password "<PASSWORD_SEGURO>" `
    --sku-name Standard_B1ms `
    --tier Burstable `
    --storage-size 32 `
    --version 16 `
    --public-access 0.0.0.0   # permite acceso desde Container Apps (ajustar con firewall rules)

# Crear base de datos
az postgres flexible-server db create `
    --resource-group $RESOURCE_GROUP `
    --server-name ligamaster-db `
    --database-name laliga
```

> **Importante:** La BD de Azure PostgreSQL es **persistente**. Los datos no se borran cuando el contenedor se reinicia. Solo se pobla en el primer despliegue (cuando hay <500 jugadores).

#### 4.5 Crear Aiven OpenSearch

1. Ir a [aiven.io](https://aiven.io) → **Create service** → **OpenSearch**
2. Plan: **Startup-4** (mínimo recomendado) en Azure West Europe
3. Anotar: `Service URI`, `User`, `Password`
4. El host tiene formato: `ligamaster-os.aivencloud.com:27234`

#### 4.6 Crear Container Apps Environment

```bash
az containerapp env create `
    --name $ENV_NAME `
    --resource-group $RESOURCE_GROUP `
    --location $LOCATION
```

#### 4.7 Desplegar backend

```bash
az containerapp create `
    --name ligamaster-backend `
    --resource-group $RESOURCE_GROUP `
    --environment $ENV_NAME `
    --image "$ACR_NAME.azurecr.io/ligamaster-backend:latest" `
    --registry-server "$ACR_NAME.azurecr.io" `
    --registry-username $ACR_NAME `
    --registry-password $ACR_PASSWORD `
    --target-port 8000 `
    --ingress external `
    --min-replicas 1 `
    --max-replicas 2 `
    --cpu 1.0 --memory 2.0Gi `
    --env-vars `
        SECRET_KEY="<SECRET_KEY_LARGA>" `
        DEBUG="False" `
        DJANGO_SETTINGS_MODULE="config.settings" `
        DB_NAME="laliga" `
        DB_USER="laliga_admin" `
        DB_PASSWORD="<DB_PASSWORD>" `
        DB_HOST="ligamaster-db.postgres.database.azure.com" `
        DB_PORT="5432" `
        DB_SSL="require" `
        OPENSEARCH_HOST="<host_aiven>:<puerto>" `
        OPENSEARCH_USER="avnadmin" `
        OPENSEARCH_PASSWORD="<OS_PASSWORD>" `
        OPENSEARCH_USE_SSL="True" `
        API_FOOTBALL_KEY="<tu_clave>"

# Obtener la URL del backend
$BACKEND_URL = $(az containerapp show `
    --name ligamaster-backend `
    --resource-group $RESOURCE_GROUP `
    --query properties.configuration.ingress.fqdn -o tsv)
Write-Host "Backend URL: https://$BACKEND_URL"
```

#### 4.8 Actualizar EXTRA_ALLOWED_HOSTS y CORS

```bash
az containerapp update `
    --name ligamaster-backend `
    --resource-group $RESOURCE_GROUP `
    --set-env-vars `
        EXTRA_ALLOWED_HOSTS="$BACKEND_URL" `
        EXTRA_CORS_ORIGINS="https://<URL_FRONTEND_CUANDO_LA_TENGAS>"
```

#### 4.9 Desplegar frontend

```bash
# Rebuild con la URL real del backend
docker build `
    --build-arg VITE_API_URL="https://$BACKEND_URL" `
    -t "$ACR_NAME.azurecr.io/ligamaster-frontend:latest" `
    ./frontend-web
docker push "$ACR_NAME.azurecr.io/ligamaster-frontend:latest"

az containerapp create `
    --name ligamaster-frontend `
    --resource-group $RESOURCE_GROUP `
    --environment $ENV_NAME `
    --image "$ACR_NAME.azurecr.io/ligamaster-frontend:latest" `
    --registry-server "$ACR_NAME.azurecr.io" `
    --registry-username $ACR_NAME `
    --registry-password $ACR_PASSWORD `
    --target-port 80 `
    --ingress external `
    --min-replicas 1 --max-replicas 2 `
    --cpu 0.25 --memory 0.5Gi
```

#### 4.10 Verificar despliegue

```bash
curl "https://$BACKEND_URL/health/"
# → {"status": "ok"}

curl "https://$BACKEND_URL/api/jugadores/?page=1"
```

---

## 5. Referencia de variables de entorno

| Variable | Local | Docker | Render | Azure | Descripción |
|----------|-------|--------|--------|-------|-------------|
| `SECRET_KEY` | cualquiera | cambiar | **obligatoria** | **obligatoria** | Clave secreta Django |
| `DEBUG` | `True` | `True` | `False` | `False` | Modo debug |
| `DATABASE_URL` | — | — | auto (Render) | — | URL completa PostgreSQL |
| `DB_NAME` | `laliga` | `laliga` | — | `laliga` | Nombre BD |
| `DB_USER` | `laliga_user` | `laliga_user` | — | `laliga_admin` | Usuario BD |
| `DB_PASSWORD` | tu pw | tu pw | — | **obligatoria** | Password BD |
| `DB_HOST` | `localhost` | `db` | — | `*.postgres.database.azure.com` | Host BD |
| `DB_SSL` | — | — | — | `require` | SSL para Azure |
| `OPENSEARCH_HOST` | `localhost:9200` | `opensearch:9200` | `host:443` | `host:port` | Host OpenSearch |
| `OPENSEARCH_USE_SSL` | `False` | `False` | `True` | `True` | SSL OpenSearch |
| `EXTRA_ALLOWED_HOSTS` | — | — | `app.onrender.com` | `app.azurecontainerapps.io` | Hosts adicionales |
| `EXTRA_CORS_ORIGINS` | — | — | `https://...` | `https://...` | Orígenes CORS |
| `API_FOOTBALL_KEY` | tu clave | tu clave | tu clave | tu clave | Clave API-Football |

---

## 6. Preguntas frecuentes

### ¿Cuánto tarda el primer arranque?

El pipeline completo de inicialización (carga de datos CSV, cálculo de percentiles, entrenamiento de modelos, predicciones, indexado OpenSearch) tarda entre **10 y 25 minutos** dependiendo de los recursos del contenedor.

Los arranques posteriores (cuando la BD ya tiene ≥500 jugadores y ≥100 predicciones) tardan **~30 segundos**.

### ¿Se borran los datos cuando reinicio el contenedor en Azure?

**No.** Azure Database for PostgreSQL Flexible Server es un servicio gestionado completamente independiente del contenedor. Los datos persisten indefinidamente aunque el contenedor se reinicie, actualice o elimine. Solo se perderían si borras explícitamente el servidor de BD.

### ¿El healthcheck falla durante el primer arranque?

Sí, es normal. El healthcheck tiene un `start_period` de 120-180s en los compose de Render/Azure para dar tiempo al primer arranque. Durante ese tiempo los fallos del healthcheck se ignoran.

### ¿Cómo forzar una repoblación desde cero?

Con Docker local:
```bash
docker compose down -v    # borra el volumen postgres
docker compose up --build
```

Con Azure: borra y recrea el servidor PostgreSQL (operación destructiva, hazlo con cuidado).

### ¿Cómo actualizar la aplicación sin perder datos?

```bash
# 1. Build nuevas imágenes
docker build -t "$ACR_NAME.azurecr.io/ligamaster-backend:latest" .
docker push "$ACR_NAME.azurecr.io/ligamaster-backend:latest"

# 2. Forzar actualización (Container Apps hace rolling update)
az containerapp update --name ligamaster-backend --resource-group $RESOURCE_GROUP `
    --image "$ACR_NAME.azurecr.io/ligamaster-backend:latest"
```

La BD no se toca en el update — el entrypoint detecta ≥500 jugadores y salta la inicialización.

### ¿Cómo generar un SECRET_KEY seguro?

```bash
python -c "import secrets; print(secrets.token_hex(50))"
```

---

## 7. Estructura de archivos de entorno

```
.env.local    ← desarrollo sin Docker (en Git, valores de ejemplo)
.env.docker   ← desarrollo con Docker (en Git, valores de ejemplo)
.env.render   ← pre-producción Render (IGNORADO por Git — contiene secretos)
.env.azure    ← producción Azure     (IGNORADO por Git — contiene secretos)
.env          ← copia activa para docker compose local (IGNORADO por Git)
```
