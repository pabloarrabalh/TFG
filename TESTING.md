# Testing Suite - LigaMaster

## Herramientas de Testing

### 1. **Django TestCase + unittest**
- **Propósito**: Tests unitarios, integración y E2E  
- **Ubicación**: `main/tests/test_*.py`
- **Características**:
  - Aislamiento de BD por test (SQLite para local, PostgreSQL en producción)
  - Setup de datos con `setUpTestData` (optimizado, compartido entre tests)
  - Fixtures y fixtures en memoria
  - Validación automática de modelos

**Ejemplos de uso**:
```python
from django.test import TestCase

class MyTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        # Setup compartido entre todos los tests de esta clase
        cls.user = User.objects.create_user('test', 'test@test.com', 'pass')
    
    def test_something(self):
        # Cada test obtiene una copia de setUpTestData
        response = self.client.get('/api/endpoint/')
        self.assertEqual(response.status_code, 200)
```

**Ubicación**: `main/tests/test_modelos.py`, `test_integracion.py`, etc.

### 2. **DRF SimpleTestCase + APITestCase**
- **Propósito**: Tests de API REST con cliente HTTP integrado
- **Características**:
  - `self.client.get()`, `self.client.post()`, etc.
  - Soporte para JSON, formularios, archivos
  - Assertions específicas para HTTP (status_code, content_type, etc.)
  - Auth: `self.client.force_login(user)` o headers CSRF

**Ejemplos de uso**:
```python
from django.test import TestCase
from rest_framework.test import APITestCase

class ApiTestCase(APITestCase):
    def test_endpoint(self):
        response = self.client.post('/api/auth/login/', {
            'username': 'test',
            'password': 'pass'
        })
        self.assertEqual(response.status_code, 200)
        self.assertIn('user', response.json())
```

### 3. **coverage.py**
- **Propósito**: Medir cobertura de código  
- **Configuración**: `.coveragerc` (65% threshold)
- **Módulos bajo cobertura**:
  - `main.models` (92.45%) ✅
  - `main.api.auth` (80.56%) ✅
  - `main.api.clasificacion` (58.54%) ⚠️
  - `main.scrapping.matching` (61.07%) ⚠️

**Ejecutar cobertura**:
```bash
python manage.py test main.tests --keepdb
python -m coverage report -m
python -m coverage html  # Genera reporte HTML
```

### 4. **Locust**
- **Propósito**: Tests de carga y performance  
- **Ubicación**: `main/tests/locustfile.py`
- **Características**:
  - HttpUser tasks con pesos
  - on_start bootstrap (GET /api/me para sesión)
  - Validación explícita (catch_response)
  - Random scenarios (jornadas, usuarios)

**Ejecutar Locust**:
```bash
# Headless (sin UI)
python -m locust -f main/tests/locustfile.py \
  --host http://127.0.0.1:8000 \
  --users 5 --spawn-rate 2 --run-time 15s \
  --headless --only-summary

# Con UI web
python -m locust -f main/tests/locustfile.py \
  --host http://127.0.0.1:8000
# Abre http://localhost:8089
```

**Estructura Locust**:
```python
from locust import HttpUser, task, between

class LigaMasterApiUser(HttpUser):
    wait_time = between(0.3, 1.5)
    
    def on_start(self):
        # Ejecuta UNA VEZ al iniciar la sesión
        self.client.get("/api/me/")
    
    @task(4)  # Weight: 4 (ejecuta 4 veces más que otros tasks)
    def me(self):
        with self.client.get("/api/me/", catch_response=True) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Got status {response.status_code}")
    
    @task(2)
    def other_task(self):
        # ...
```

---

## Estructura de Tests

```
main/tests/
├── __init__.py
├── test_modelos.py              # Unit tests (models validation)
├── test_integracion.py          # Integration tests (DB + API)
├── test_e2e.py                  # E2E tests (full auth cycle)
├── test_matching.py             # Matching logic tests
├── test_errores.py              # Error cases (401, 400, 404)
├── test_casos_especiales.py     # Specific case tests
├── test_api.py                  # COMPREHENSIVE API TESTS (46 tests, todos endpoints)
└── locustfile.py                # Load testing with Locust
```

### test_api_comprehensive.py - Endpoints Cubiertos ✅

**Auth Endpoints (9 tests)**:
- ✅ GET /api/me/ (authenticated + unauthenticated)
- ✅ POST /api/auth/login/ (valid, invalid, email fallback)
- ✅ POST /api/auth/logout/
- ✅ POST /api/auth/register/ (valid, password mismatch, duplicate user)

**Team Endpoints (3 tests)**:
- ✅ GET /api/equipos/
- ✅ GET /api/equipo/<nombre>/
- ✅ GET /api/equipo/<nombre>/ (nonexistent → 404)

**Player Endpoints (3 tests)**:
- ✅ GET /api/jugador/<id>/
- ✅ GET /api/jugador/<id>/ (nonexistent → 404)
- ✅ GET /api/top-jugadores-por-posicion/

**Classification Endpoints (2 tests)**:
- ✅ GET /api/clasificacion/
- ✅ GET /api/clasificacion/?temporada=&jornada=

**Favorites Endpoints (3 tests)**:
- ✅ GET /api/favoritos/ (auth + unauth)
- ✅ POST /api/favoritos/toggle-v2/

**Profile Endpoints (3 tests)**:
- ✅ GET /api/perfil/ (auth + unauth)
- ✅ PATCH /api/perfil/update/

**Menu Endpoints (2 tests)**:
- ✅ GET /api/menu/
- ✅ GET /api/menu/?jornada=

**Notification Endpoints (4 tests)**:
- ✅ GET /api/notificaciones/ (auth + unauth)
- ✅ POST /api/notificaciones/<id>/leer/
- ✅ POST /api/notificaciones/<id>/borrar/

**Search Endpoints (1 test)**:
- ✅ GET /api/buscar/?q=query

**Health & Integration (2 tests)**:
- ✅ GET /health/
- ✅ Integration: register → login → profile → logout (smoke test)

---

## Guía Rápida

### Ejecutar todos los tests
```bash
python manage.py test main.tests
```

### Ejecutar test específico
```bash
python manage.py test main.tests.test_modelos
python manage.py test main.tests.test_api
python manage.py test main.tests.test_e2e
```

### Con cobertura
```bash
python manage.py test main.tests --keepdb
python -m coverage report -m
python -m coverage html
```

### Locust load testing
```bash
# Terminal 1: Inicia servidor
python manage.py runserver 127.0.0.1:8000

# Terminal 2: Corre Locust
python -m locust -f main/tests/locustfile.py \
  --host http://127.0.0.1:8000 \
  --users 10 --spawn-rate 2 --run-time 30s --headless
```

---

## Estadísticas Actuales

| Métrica | Valor |
|---------|-------|
| Tests unitarios/integración | 14 ✅ |
| Cobertura total | 77.13% ✅ |
| Threshold | 65% (Cumple) ✅ |
| Endpoints API cubiertos | ~28 endpoints |
| Cargas Locust | 7 task methods |

---

## Checklist de Testing (test_modelos.py)
- [x] Integration tests (API + BD) - 2 tests (test_integracion.py)
- [x] E2E tests (user journey) - 1 test (test_e2e.py)
- [x] Negative/error tests (casos fallida) - 3 tests (test_errores.py)
- [x] Matching logic tests - 3 tests (test_matching.py)
- [x] **Comprehensive API tests - 30 tests (test_api.py)**
- [x] Casos especiales - 1 test (test_casos_especiales.py)
- [x] Matching logic tests - 3 tests
- [x] **Comprehensive API tests - 30 tests (todos endpoints principales)**
- [x] Coverage.py setup + 65% gate (77.13% cumplido)
- [x] Locust load testing
- [x] Requirements unificado (requirements.txt único)
- [x] TESTING.md documentation
- [x] **Total: 46 tests, todos pasando ✅**
