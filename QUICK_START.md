# 🚀 INICIAR APLICACIÓN

Tienes **dos opciones**: LOCAL o DOCKER

---

## 🖥️ **OPCIÓN 1: LOCAL (sin Docker)**

### Terminal 1: OpenSearch
```powershell
.\start-opensearch-local.ps1
```

### Terminal 2: Django + Frontend
```powershell
# Activar venv
& .\.venv311\Scripts\Activate.ps1

# Django
python manage.py runserver
```

### Terminal 3: Frontend (en otra carpeta)
```powershell
cd frontend-web
npm run dev
```

**Acceso**: http://localhost:5173

📖 [Guía detallada: SETUP_LOCAL_NO_DOCKER.md](SETUP_LOCAL_NO_DOCKER.md)

---

## 🐳 **OPCIÓN 2: DOCKER (recomendado para resetear todo)**

```powershell
.\use-docker-env.ps1
.\run-all.ps1
```

Y en otra terminal:
```powershell
cd frontend-web
npm run dev
```

**Acceso**: http://localhost:8000

📖 [Guía detallada: OPENSEARCH_SETUP.md](OPENSEARCH_SETUP.md)

---

## 🛠️ **Scripts disponibles**

| Script | Propósito | 
|--------|-----------|
| `use-local-env.ps1` | Activa config LOCAL (.env.local) |
| `use-docker-env.ps1` | Activa config DOCKER (.env.docker) |
| `start-opensearch-local.ps1` | Descarga e inicia OpenSearch localmente |
| `run-all.ps1` | Inicia TODO en Docker |
| `start-opensearch.ps1` | Inicia Docker compose |
| `stop-opensearch.ps1` | Detiene Docker compose |
| `status-opensearch.ps1` | Ver estado de Docker |

---

## 🎯 Resumen rápido

### **LOCAL (desarrollo rápido)**
```powershell
# Terminal 1
.\start-opensearch-local.ps1

# Terminal 2
& .\.venv311\Scripts\Activate.ps1; python manage.py runserver

# Terminal 3
cd frontend-web; npm run dev
```

### **DOCKER (limpio + reset)**
```powershell
# Una linea lo hace todo:
.\run-all.ps1

# Terminal 2: Frontend
cd frontend-web; npm run dev
```
