# 🚀 GUÍA RÁPIDA: INICIAR OPENSEARCH + DJANGO

## ✅ Prerequisites
- **Docker Desktop** instalado (descargalo de https://www.docker.com/products/docker-desktop si no lo tienes)
- **PowerShell** en Windows
- Estar en la carpeta `C:\Users\pablo\Desktop\TFG`

---

## 📋 PASO A PASO

### **PASO 1: Iniciar OpenSearch en Docker** (Terminal 1)

Abre una terminal PowerShell en `C:\Users\pablo\Desktop\TFG` y ejecuta:

```powershell
.\start-opensearch.ps1
```

**Qué hace:**
- ✓ Verifica que Docker está instalado
- ✓ Inicia PostgreSQL + OpenSearch
- ✓ Espera a que OpenSearch esté listo
- ✓ Muestra: `✅ OpenSearch ESTÁ LISTO EN http://localhost:9200`

**Esto tarda ~30 segundos la primera vez**, luego es más rápido.

**Debería ver algo como:**
```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🚀 INICIANDO OPENSEARCH EN DOCKER
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
...
✅ OpenSearch ESTÁ LISTO EN http://localhost:9200
```

**⚠️ NO CIERRES ESTA TERMINAL**, déjala abierta de fondo.

---

### **PASO 2: Activar venv + Iniciar Django** (Terminal 2)

Abre una **nueva terminal PowerShell** en la misma carpeta y ejecuta:

```powershell
# Activar virtual environment
& .\.venv311\Scripts\Activate.ps1

# Iniciar servidor Django
python manage.py runserver
```

**Debería ver algo como:**
```
Django version 4.x.x, using settings 'config.settings'
Starting development server at http://127.0.0.1:8000/
...
🔍 Indexando documentos en OpenSearch...
✓ OpenSearch indexado correctamente
```

**Si ves esto, ¡ESTÁ FUNCIONANDO!** ✅

---

### **PASO 3: Verificar que funciona**

**Test 1: Abrir el navegador**
```
http://localhost:8000
```
Debería cargar la aplicación sin errores.

**Test 2: Probar la búsqueda**
- Ve a la página de Estadísticas
- Usa la barra de búsqueda
- Busca un jugador (ej: "Messi", "Ronaldo")
- Debería mostrar resultados

**Test 3: Verificar OpenSearch directamente**

En PowerShell:
```powershell
# Checkear estado
.\status-opensearch.ps1

# O manual:
curl.exe -u admin:Admin_Password1! http://localhost:9200/_cluster/health
```

---

## 🛑 Cómo Detener

Cuando quieras apagar OpenSearch, ejecuta en la Terminal 1:

```powershell
.\stop-opensearch.ps1
```

---

## ⚠️ Troubleshooting

### "Docker no está instalado"
**Solución**: Descargalo de https://www.docker.com/products/docker-desktop

### "OpenSearch no responde"
**Solución**: Espera 30 segundos y ejecuta:
```powershell
.\status-opensearch.ps1
```

### "Error de conexión a OpenSearch"
**Solución 1**: Verifica que docker está corriendo:
```powershell
docker ps
```

**Solución 2**: Reinicia Docker:
```powershell
docker-compose restart opensearch
```

### "La búsqueda devuelve error 503"
**Problema**: OpenSearch no está indexado o no responde

**Solución**: 
1. Verifica que OpenSearch está corriendo (`.\status-opensearch.ps1`)
2. Reinicia Django:
   ```powershell
   python manage.py runserver
   ```

---

## 📊 Credenciales

- **OpenSearch**:
  - Usuario: `admin`
  - Contraseña: `Admin_Password1!`
  - Host: `http://localhost:9200`

- **PostgreSQL**:
  - Usuario: `user1`
  - Contraseña: `user1`
  - BD: `laliga`

---

## 🔧 Comandos útiles

```powershell
# Ver logs en tiempo real
docker-compose logs -f opensearch

# Ver todos los contenedores
docker-compose ps

# Entrar al bash de OpenSearch
docker-compose exec opensearch /bin/bash

# Limpiar todo (cuidado!):
docker-compose down -v  # Elimina volúmenes también
```

---

## ✅ Resumen Rápido

| Paso | Comando | Terminal |
|------|---------|----------|
| 1. Iniciar Docker | `.\start-opensearch.ps1` | Nueva #1 |
| 2. Activar venv | `& .\.venv311\Scripts\Activate.ps1` | Nueva #2 |
| 3. Iniciar Django | `python manage.py runserver` | Misma #2 |
| 4. Abrir navegador | `http://localhost:8000` | Navegador |
| 5. Buscar en la app | Ir a Estadísticas → Usar buscador | ✅ Funciona |

---

**¿Listo? ¡Ejecuta y listo!** 🚀
