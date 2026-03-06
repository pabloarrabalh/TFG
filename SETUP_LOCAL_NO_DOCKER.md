# 🚀 GUÍA: SIN DOCKER (LOCAL)

**Para correr sin Docker, con `runserver` y `npm run dev`:**

---

## 📋 PASO 1: Activar configuración LOCAL

```powershell
.\use-local-env.ps1
```

Esto:
- ✓ Cambia a `.env.local`
- ✓ OpenSearch apunta a `localhost:9200`
- ✓ PostgreSQL local

---

## 🔍 PASO 2: Iniciar OpenSearch (Terminal 1)

```powershell
.\start-opensearch-local.ps1
```

**Primera vez:**
- 📥 Descarga OpenSearch (~700MB)
- 📦 Extrae automáticamente
- 🚀 Inicia OpenSearch

**Veces siguientes:**
- ⚡ Solo inicia OpenSearch (muy rápido)

**Debería ver:**
```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
✅ OpenSearch iniciado
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📍 Endpoint: http://localhost:9200
🔐 Usuario: admin
🔑 Contraseña: admin

✨ ¡OpenSearch está listo!
```

**⚠️ NO CIERRES ESTA TERMINAL**, déjala abierta.

---

## 🐍 PASO 3: Django (Terminal 2)

```powershell
cd C:\Users\pablo\Desktop\TFG
& .\.venv311\Scripts\Activate.ps1
python manage.py runserver
```

Debería ver:
```
...
🔍 Indexando documentos en OpenSearch...
✓ OpenSearch indexado correctamente
Starting development server at http://127.0.0.1:8000/
```

---

## ⚛️ PASO 4: Frontend (Terminal 3)

```powershell
cd C:\Users\pablo\Desktop\TFG\frontend-web
npm run dev
```

---

## ✅ PASO 5: Verifica que funciona

1. **Abre**: http://localhost:5173 (o el Puerto que sugiera npm)
2. **Ve a Estadísticas**
3. **Busca un jugador** en la barra de búsqueda
4. **Debería mostrar resultados** ✅

---

## 📊 Configuraciones

### Archivo: `.env.local`
```env
OPENSEARCH_HOST=localhost:9200  # ← LOCAL
OPENSEARCH_USER=admin
OPENSEARCH_PASSWORD=admin
DB_PORT=5432  # ← PostgreSQL LOCAL
```

### Archivo: `.env.docker`
```env
OPENSEARCH_HOST=opensearch:9200  # ← EN CONTENEDOR
OPENSEARCH_USER=admin
OPENSEARCH_PASSWORD=Admin_Password1!
```

---

## 🔄 Cambiar entre LOCAL y DOCKER

**Para usar LOCAL:**
```powershell
.\use-local-env.ps1
```

**Para usar DOCKER:**
```powershell
.\use-docker-env.ps1
.\run-all.ps1
```

---

## 🛑 Detener OpenSearch local

En la Terminal 1 (donde está OpenSearch), presiona:
```
CTRL+C
```

---

## 📁 Estructura de archivos

```
TFG/
├── .env              ← ACTUAL (se sobreescribe según el que uses)
├── .env.local        ← Para desarrollo sin Docker
├── .env.docker       ← Para desarrollo con Docker
├── use-local-env.ps1    ← Activar config LOCAL
├── use-docker-env.ps1   ← Activar config DOCKER
├── start-opensearch-local.ps1  ← Inicia OpenSearch local
├── run-all.ps1       ← Inicia TODO con Docker
└── ...
```

---

## 🐛 Troubleshooting

### "OpenSearch no responde"
```powershell
# Verifica que opensearch.bat está corriendo
Get-Process | grep java

# Si no, inicia de nuevo:
.\start-opensearch-local.ps1
```

### "Error importando OpenSearch"
```powershell
# Verifica que .env.local está activo:
cat .env | grep OPENSEARCH_HOST
# Debería estar: localhost:9200
```

### "Descarga de OpenSearch muy lenta"
Puedes [descargarlo manualmente](https://opensearch.org/downloads/opensearch) y guardarlo en la carpeta raíz.

---

## 💡 Notas

- **OpenSearch local** es perfecto para desarrollo
- **Usa Docker** cuando quieras "resetear" todo fácilmente
- **El cambio de .env** es instantáneo (busca la siguiente vez que reinicies Django)

---

**¡Listo! Sigue los pasos y listo 🚀**
