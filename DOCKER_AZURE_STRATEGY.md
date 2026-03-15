# ESTRATEGIA SIMPLIFICADA: DOCKER + AZURE

## Resumen de cambios

✅ **Un único `docker-compose.yml`** → Sin archivos prod/dev  
✅ **Entrypoint simplificado** → `docker-entrypoint.sh` que gestiona todo  
✅ **Predicciones bajo demanda + background** → Sin Celery, sin complejidad extra  
✅ **Compatible con Azure Container Instances / App Service**  

---

## Comportamiento de predicciones

### Fase 1: Inicial (primeros 30-60 segundos)
```
docker-compose up -d
  ↓
• Executar migraciones
• Generar predicciones para jugadores con ≥60 minutos en jornada 10
• Iniciar servidor Django
• Lanzar worker en background
```

### Fase 2: Background continuo (8 horas)
- Genera predicciones para jugadores sin predecir
- Batch de 50 jugadores cada 30 segundos
- NO bloquea las requests normales

### Fase 3: Bajo demanda
- Cuando accedes a `/plantilla` → Genera predicciones del equipo al vuelo
- Cuando accedes a `/jugador/{id}` → Genera predicción del jugador
- Implementado en las vistas Django

---

## Uso local (desarrollo)

```bash
# 1. Compilar y levantar
docker-compose up -d

# 2. Verificar logs
docker-compose logs -f backend

# 3. Acceder
# Frontend: http://localhost
# API: http://localhost:8000

# 4. Parar
docker-compose down

# 5. Limpiar todo (BD, etc)
docker-compose down -v
```

---

## Despliegue en Azure

### Opción A: Azure Container Instances (más simple, serverless)

```bash
# 1. Crear grupo de recursos
az group create --name myapp-rg --location westeurope

# 2. Crear Azure Container Registry
az acr create --resource-group myapp-rg --name myappregistry --sku Basic

# 3. Buildear y subir imagen backend
docker build -t myapp-backend:latest .
az acr build --registry myappregistry --image myapp-backend:latest .

# 4. Crear instancia PostgreSQL en Azure Database
az postgres flexible-server create \
  --resource-group myapp-rg \
  --name myapp-db \
  --admin-user dbadmin \
  --admin-password MySecurePassword123! \
  --sku-name Standard_B1ms \
  --tier Burstable

# 5. Desplegar con ACI
az container create \
  --resource-group myapp-rg \
  --name myapp-backend \
  --image myappregistry.azurecr.io/myapp-backend:latest \
  --environment-variables \
    DB_HOST=myapp-db.postgres.database.azure.com \
    DB_NAME=myappdb \
    DB_USER=dbadmin \
    OPENSEARCH_HOST=... \
  --ports 8000 \
  --cpu 1 \
  --memory 1
```

### Opción B: Azure App Service (recomendado para producción)

```bash
# 1. Crear plan App Service
az appservice plan create \
  --name myapp-plan \
  --resource-group myapp-rg \
  --is-linux \
  --sku B2

# 2. Crear App Service
az webapp create \
  --resource-group myapp-rg \
  --plan myapp-plan \
  --name myapp-backend \
  --deployment-container-image-name myappregistry.azurecr.io/myapp-backend:latest

# 3. Configurar variables de entorno
az webapp config appsettings set \
  --resource-group myapp-rg \
  --name myapp-backend \
  --settings DB_HOST=myapp-db.postgres.database.azure.com \
             DB_NAME=myappdb \
             DB_USER=dbadmin \
             DB_PASSWORD=... \
             DEBUG=false
```

---

## Respuestas a tus preguntas

### ¿Poblando BD una vez es suficiente?

**SÍ → El entrypoint solo crea datos si la BD está vacía.**

Cuando despliegas:
- **Primera vez**: Ejecuta migraciones + genera datos iniciales
- **Siguiente**: Solo ejecuta migraciones pendientes (sin volver a cargar datos)
- **Futuras**: El contenedor reutiliza la BD existente

```python
# En tu management command
import os
from django.core.management.base import BaseCommand
from django.db.models import Count

class Command(BaseCommand):
    def handle(self, *args, **options):
        # Solo generar si no hay datos
        if User.objects.count() == 0:
            self.stdout.write("Populando BD...")
            # Cargar datos
        else:
            self.stdout.write("BD ya poblada, skipping...")
```

### ¿Luego solo llamar al servicio?

**SÍ → Exactamente:**

```
Tu cliente → (llamadas HTTPS) → Azure App Service
                                        ↓
                                    Django app
                                        ↓
                      PostgreSQL (datos persistentes)
                      OpenSearch (índices)
```

El contenedor no almacena datos. Todo persistente va en la BD.

### ¿Azure Container Registry + App Service es buena estrategia?

**SÍ → Es la estrategia recomendada:**

| Servicio | Uso |
|----------|-----|
| **Azure Container Registry** | Guardar tu imagen Docker (`myapp-backend:latest`) |
| **Azure App Service** | Ejecutar el contenedor (auto-scale, https, custom domains) |
| **Azure Database for PostgreSQL** | BD relacional (backups automáticos, Azure Backup) |
| **Azure Cognitive Search / OpenSearch** (optional) | Búsqueda (OpenSearch en VM o ACI si no hay managed service en Azure) |

---

## Pasos detallados para Azure (primeras 2 horas)

### 1. Preparar .env para Azure
```bash
# .env.azure
DB_HOST=myapp-db.postgres.database.azure.com
DB_NAME=myappdb
DB_USER=dbadmin
DB_PASSWORD=TuPasswordSeguro123!
OPENSEARCH_HOST=openearch-vm.eastus.cloudapp.azure.com:9200
DEBUG=false
ALLOWED_HOSTS=myapp-backend.azurewebsites.net
SECRET_KEY=...generado-aleatorio...
```

### 2. Build & Push a Registry
```bash
# Login a ACR
az acr login --name myappregistry

# Build
docker build -t myapp-backend:latest .

# Tag para registry
docker tag myapp-backend:latest myappregistry.azurecr.io/myapp-backend:latest

# Push
docker push myappregistry.azurecr.io/myapp-backend:latest
```

### 3. Crear BD PostgreSQL
```bash
az postgres flexible-server create \
  --resource-group myapp-rg \
  --name myapp-db \
  --admin-user dbadmin \
  --admin-password TuPasswordSeguro123! \
  --sku-name Standard_B1ms \
  --tier Burstable \
  --storage-size 32
```

### 4. Crear App Service
```bash
# Plan
az appservice plan create \
  --name myapp-plan \
  --resource-group myapp-rg \
  --is-linux \
  --sku B2  # 2 CPU, 3.5GB RAM (suficiente para empezar)

# App
az webapp create \
  --resource-group myapp-rg \
  --plan myapp-plan \
  --name myapp-backend \
  --deployment-container-image-name myappregistry.azurecr.io/myapp-backend:latest \
  --docker-registry-server-url https://myappregistry.azurecr.io \
  --docker-registry-server-user <username> \
  --docker-registry-server-password <password>
```

### 5. Configurar conexión a BD
```bash
az webapp config appsettings set \
  --resource-group myapp-rg \
  --name myapp-backend \
  --settings \
    WEBSITES_PORT=8000 \
    DB_HOST=myapp-db.postgres.database.azure.com \
    DB_NAME=myappdb \
    DB_USER=dbadmin \
    DB_PASSWORD=TuPasswordSeguro123! \
    OPENSEARCH_HOST=openearch-vm:9200 \
    DEBUG=false
```

---

## Limpieza de archivos antiguos

Ya no necesitas:
```bash
# Borrar estos archivos (ya están en el nuevo docker-compose.yml)
rm -f docker-compose-prod.yml
rm -f docker-compose-dev.yml
rm -f entrypoint-prod.sh
rm -f entrypoint-dev.sh
rm -f setup-dev.sh
rm -f setup-prod.sh
rm -f docker-compose-old.yml  (si existe)

# Mantener solo
✓ docker-compose.yml
✓ docker-entrypoint.sh
✓ Dockerfile
```

---

## Cheatsheet de comandos

```bash
# Local
docker-compose up -d              # Levantar
docker-compose down               # Parar
docker-compose logs -f backend    # Logs

# Azure
az login                                              # Autenticar
az acr build --registry myappregistry --image app .  # Build & push
az webapp deployment container config \
  --name myapp-backend \
  --resource-group myapp-rg \
  --enable-cd true                                   # Auto-deploy en push
```

---

## Próximos pasos (opcionales para mejorar)

1. **Celery + Redis** para predicciones más robustas (si el background threading no es suficiente)
2. **Azure Key Vault** para guardar secrets (DB password, etc)
3. **Application Insights** para monitoreo
4. **Azure Front Door** para CDN y distributed caching
5. **GitHub Actions** para CI/CD automático

¿Alguna pregunta sobre esta estrategia?
