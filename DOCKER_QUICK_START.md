# Dockerización Simplificada (2024)

## 🎯 Objetivo
Un único `docker-compose.yml` que:
- ✅ Levanta toda la app en 2 comandos
- ✅ Puebla la BD automáticamente la primera vez
- ✅ Genera predicciones en background sin parar
- ✅ Es compatible con Azure

---

## 🚀 Inicio rápido (LOCAL)

### Requisitos
```bash
docker --version          # 20.10+
docker-compose --version  # 2.0+
```

### Levantar la app
```bash
# 1. Compilar y levantar (primera vez: 2-3 min)
docker-compose up -d

# 2. Ver logs
docker-compose logs -f backend

# 3. Acceder
# Frontend: http://localhost
# API: http://localhost:8000/api/
```

### Parar / Limpiar
```bash
docker-compose down           # Parar (BD persiste)
docker-compose down -v        # Parar y borrar BD
docker-compose restart        # Reiniciar
```

---

## 📋 Qué hace el entrypoint automáticamente

```
docker-compose up -d
    ↓
1️⃣  Ejecutar migraciones (1-2 seg)
2️⃣  Generar predicciones iniciales para jugadores con 60+ minutos (30-60 seg)
3️⃣  Iniciar servidor Django (puerto 8000)
4️⃣  Lanzar worker en background generando predicciones (8 horas)
```

---

## 🔧 Mantenimiento

### Ver estado
```bash
docker-compose ps
docker-compose logs backend    # últimos 100 líneas
docker-compose logs -f backend # seguir en tiempo real
```

### Acceder a Django shell
```bash
docker-compose exec backend python manage.py shell
```

### Migraciones manuales
```bash
docker-compose exec backend python manage.py migrate
docker-compose exec backend python manage.py createsuperuser
```

### Reconstruir imagen
```bash
docker-compose build --no-cache
docker-compose up -d
```

---

## 🌐 Despliegue en Azure

Ver [DOCKER_AZURE_STRATEGY.md](./DOCKER_AZURE_STRATEGY.md) para instrucciones detalladas.

**Resumen: 4 pasos**
```bash
# 1. Build & push a Azure Container Registry
az acr build --registry myregistry --image myapp .

# 2. Crear BD PostgreSQL
az postgres flexible-server create --name mydb ...

# 3. Crear App Service
az webapp create --name myapp ...

# 4. Configurar variables de entorno
az webapp config appsettings set --name myapp --settings ...
```

---

## 📁 Archivos importantes

```
.
├── docker-compose.yml          # ✅ UN archivo para todo
├── Dockerfile                  # Imagen backend
├── docker-entrypoint.sh        # Script inicio (migraciones + predict)
├── frontend-web/
│   └── Dockerfile              # Imagen frontend (Nginx)
├── main/
│   └── utils/
│       └── prediction_generator.py  # Lógica de predicciones
└── DOCKER_AZURE_STRATEGY.md    # Guía Azure
```

---

## ⚡ Archivos que YA NO NECESITAS

```bash
❌ docker-compose-prod.yml
❌ docker-compose-dev.yml
❌ entrypoint-prod.sh
❌ entrypoint-dev.sh
❌ setup-dev.sh
❌ setup-prod.sh
```

Puedes borrarlos:
```bash
rm -f docker-compose-{prod,dev}.yml
rm -f entrypoint-{prod,dev}.sh
rm -f setup-{dev,prod}.sh
```

---

## 🆘 Solucionar problemas

### La BD tarda en iniciarse
```bash
# Normal en primera ejecución (PostgreSQL creando volumen)
# Espera 30 segundos y reinicia si falla
docker-compose logs db
docker-compose restart db
```

### Backend no conecta a BD
```bash
# Verificar que DB está healthy
docker-compose logs db
docker-compose exec db psql -U $DB_USER -d $DB_NAME -c "SELECT 1"
```

### Vaciar y repoblar BD
```bash
docker-compose down -v         # 🗑️ Borra todo
docker-compose up -d           # Crea datos nuevos automáticamente
docker-compose logs -f backend # Ver generación de predicciones
```

### Ver predicciones en tiempo real
```bash
docker-compose logs -f backend --tail=20
# Deberías ver líneas como:
# ✓ Generando predicciones iniciales...
# ✓ Predicciones iniciales generadas
# ...
```

---

## 📊 Variables de entorno importantes

Editar `.env` según tu setup:

```env
# BD
DB_NAME=myapp_db
DB_USER=myapp_user
DB_PASSWORD=SecurePassword123!
DB_HOST=db              # En Docker siempre es "db"
DB_PORT=5432

# OpenSearch
OPENSEARCH_PASSWORD=StrongPassword123!
OPENSEARCH_USER=admin
OPENSEARCH_HOST=opensearch:9200

# Django
DEBUG=false
ALLOWED_HOSTS=localhost,127.0.0.1
SECRET_KEY=...genera-una-clave-aleatoria...

# Para Azure
GENERATE_BENCH=false    # true si quieres generar predicciones para suplentes
```

---

## 🎓 Próximos pasos

1. **Local**: Levantar y verificar que todo funciona
2. **Azure**: Seguir [DOCKER_AZURE_STRATEGY.md](./DOCKER_AZURE_STRATEGY.md)
3. **CI/CD**: Automatizar builds con GitHub Actions
4. **Monitoreo**: Agregar Application Insights de Azure

---

## 📞 Comandos rápidos

```bash
# Iniciar
docker-compose up -d

# Parar
docker-compose down

# Ver logs en tiempo real
docker-compose logs -f backend

# Ejecutar comando en backend
docker-compose exec backend python manage.py <comando>

# Acceder a base de datos
docker-compose exec db psql -U $DB_USER -d $DB_NAME

# Reconstruir (después de cambios en código)
docker-compose build && docker-compose up -d

# Limpiar todo (⚠️ BORRA BD)
docker-compose down -v && docker system prune -a
```

---

✅ **Listo. Todo simplificado en un único docker-compose.yml**
