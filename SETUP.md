# 🚀 SETUP - ULTRASIMPLE

## El único comando que necesitas

```powershell
docker-compose -f docker-compose-prod.yml up -d
```

**Eso es todo.** El sistema detecta automáticamente si la BD está llena y actúa según corresponda.

---

## Primera vez (inicial setup)
```powershell
cd C:\Users\pablo\Desktop\TFG
Copy-Item .env.example .env
docker-compose -f docker-compose-prod.yml build
docker-compose -f docker-compose-prod.yml up -d
```

Espera ~15 minutos. Verás:
```
✅ PRODUCTION READY
```

---

## Cada día después  

```powershell
docker-compose -f docker-compose-prod.yml up -d
```

El sistema detecta que la BD ya está llena y reutiliza todo (~40 segundos).

---

## Comandos útiles

```powershell
# Ver logs en directo
docker-compose -f docker-compose-prod.yml logs -f backend

# Parar (preserva datos)
docker-compose -f docker-compose-prod.yml down

# Borrar todo y empezar de cero
docker-compose -f docker-compose-prod.yml down -v
docker-compose -f docker-compose-prod.yml up -d

# Ver estado de contenedores
docker-compose -f docker-compose-prod.yml ps

# Entrar en Django shell
docker-compose -f docker-compose-prod.yml exec backend python manage.py shell
```

---

## Acceso

| Servicio | URL |
|----------|-----|
| Frontend | http://localhost:8080 |
| Backend API | http://localhost:8000 |
| OpenSearch | http://localhost:9200 |
| PostgreSQL | localhost:5432 |

---

## Cómo funciona la detección inteligente

Cuando arrancas `docker-compose up -d`, el contenedor backend ejecuta `entrypoint-prod.sh` que:

1. **Espera PostgreSQL** - Conecta y verifica que BD está lista
2. **Corre migraciones** - Aplica los esquemas necesarios
3. **Detecta datos existentes**:
   - Si `Temporada.objects.count() > 0` → **Reutiliza** (40 seg)
   - Si está vacío → **Popula** (15 min, SOLO primera vez)
4. **Arranca Daphne** - Inicia el servidor WebSocket

**Resultado:** 
```
[SKIP] Database already populated
  Temporadas: 3, Partidos: 930, Jugadores: 1017
✅ PRODUCTION READY (using existing data)
```

Solo hay **2 entrypoints**:
- `entrypoint-prod.sh` - El que actualmente usas (producción)
- `entrypoint-dev.sh` - Para desarrollo local si lo necesitas


---

## Docker Compose Files

### `docker-compose-prod.yml` (El que usas)
```yaml
db:          PostgreSQL 16
opensearch:  OpenSearch 2.11 (búsqueda)
backend:     Django + Daphne (1 réplica)
frontend:    React/Nginx (1 réplica)
```

**Volúmenes persistentes:** Los datos se guardan entre reinicios.

### `docker-compose-dev.yml`
- Para desarrollo (DEBUG=true, hot reload)
- No lo usas ahora

---

## Ciclo típico

| Paso | Comando | Tiempo |
|------|---------|--------|
| **1ª vez: Build** | `docker-compose build` | 2 min |
| **1ª vez: Start** | `docker-compose up -d` | ~15 min (popula BD) |
| **Restart** | `docker-compose down` + `up -d` | ~40 seg (reutiliza BD) |
| **Clean reset** | `docker-compose down -v` + `up -d` | ~15 min (limpia todo) |

---

## Cheatsheet rápido

```powershell
# Arrancar
docker-compose -f docker-compose-prod.yml up -d

# Ver logs
docker-compose -f docker-compose-prod.yml logs -f backend

# Parar
docker-compose -f docker-compose-prod.yml down

# Status
docker-compose -f docker-compose-prod.yml ps
```

---

## Siguiente paso

Cuando tengas esto funcionando y quieras desplegar en **Azure**, lee [AZURE_CHECKLIST.md](AZURE_CHECKLIST.md).

---

**¡Listo! Sistema en producción.** 🎉
