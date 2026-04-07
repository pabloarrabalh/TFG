import random
import json
from locust import HttpUser, between, task, events


# Pool de IDs de jugadores y equipos para simular búsquedas realistas
class LigaMasterApiUser(HttpUser):
    """Carga de APIs públicas en modo lectura para validar latencia y estabilidad.
    
    Simula usuarios navegando por:
    - Clasificaciones y equipos (lectura de datos generales)
    - Búsqueda de jugadores y detalles
    - Análisis de predicciones y rendimiento
    - Cambios de jornada (actualización de datos en caché)
    """

    wait_time = between(0.5, 2.0)
    jornadas = list(range(1, 39))  # 38 jornadas de temporada
    temporadas = ["23/24", "24/25", "25/26"]
    posiciones = ["PT", "DF", "MC", "DT"]
    
    # Pool de IDs realistas para simular búsquedas
    jugador_ids = [i for i in range(1, 501)]  # 500 jugadores
    equipo_ids = list(range(1, 21))  # 20 equipos en LaLiga

    def on_start(self):
        """Inicializa sesión al arrancar cada usuario virtual."""
        response = self.client.get("/api/me/", name="GET /api/me [bootstrap]")
        self.logged_in = response.status_code == 200

    @task(6)
    def clasificacion(self):
        """Lectura de clasificación (operación más común, caché intensivo)."""
        jornada = random.choice(self.jornadas)
        temporada = random.choice(self.temporadas)
        with self.client.get(
            "/api/clasificacion/",
            params={"temporada": temporada, "jornada": jornada},
            name="GET /api/clasificacion",
            catch_response=True,
        ) as response:
            if response.status_code in (200, 404):
                response.success()
            else:
                response.failure(f"status inesperado: {response.status_code}")

    @task(5)
    def equipos_list(self):
        """Obtener lista de equipos (operación con caché estable)."""
        with self.client.get(
            "/api/equipos/",
            name="GET /api/equipos",
            catch_response=True,
        ) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"status inesperado: {response.status_code}")

    @task(4)
    def equipo_detail(self):
        """Obtener detalles de un equipo específico."""
        equipo_id = random.choice(self.equipo_ids)
        with self.client.get(
            f"/api/equipo/{equipo_id}/",
            name="GET /api/equipo/<detail>",
            catch_response=True,
        ) as response:
            if response.status_code in (200, 404):
                response.success()
            else:
                response.failure(f"status inesperado: {response.status_code}")

    @task(5)
    def top_jugadores(self):
        """Obtener top jugadores por posición (operación de lectura caché)."""
        posicion = random.choice(self.posiciones)
        with self.client.get(
            "/api/top-jugadores-por-posicion/",
            params={"posicion": posicion},
            name="GET /api/top-jugadores-por-posicion",
            catch_response=True,
        ) as response:
            if response.status_code in (200, 400):
                response.success()
            else:
                response.failure(f"status inesperado: {response.status_code}")



    @task(4)
    def jugador_detail(self):
        """Obtener detalles de un jugador (predicciones, estadísticas)."""
        jugador_id = random.choice(self.jugador_ids)
        with self.client.get(
            f"/api/jugador/{jugador_id}/",
            name="GET /api/jugador/<detail>",
            catch_response=True,
        ) as response:
            if response.status_code in (200, 404):
                response.success()
            else:
                response.failure(f"status inesperado: {response.status_code}")

    @task(3)
    def jugador_insight(self):
        """Obtener insights/análisis de un jugador."""
        jugador_id = random.choice(self.jugador_ids)
        with self.client.get(
            "/api/jugador-insight/",
            params={"jugador_id": jugador_id},
            name="GET /api/jugador-insight",
            catch_response=True,
        ) as response:
            if response.status_code in (200, 404):
                response.success()
            else:
                response.failure(f"status inesperado: {response.status_code}")

    @task(2)
    def menu_top_jugadores(self):
        """Obtener top jugadores global para menú (caché crítica)."""
        with self.client.get(
            "/api/menu/top-jugadores/",
            name="GET /api/menu/top-jugadores",
            catch_response=True,
        ) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"status inesperado: {response.status_code}")

    @task(2)
    def cambiar_jornada(self):
        """Cambio de jornada (invalida caché de predicciones)."""
        jornada = random.choice(self.jornadas)
        with self.client.post(
            "/api/cambiar-jornada/",
            json={"jornada": jornada},
            name="POST /api/cambiar-jornada",
            catch_response=True,
        ) as response:
            if response.status_code in (200, 400):
                response.success()
            else:
                response.failure(f"status inesperado: {response.status_code}")

    @task(1)
    def health_check(self):
        """Health check para validar disponibilidad (bajo peso)."""
        with self.client.get(
            "/health/",
            name="GET /health",
            catch_response=True,
        ) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"status inesperado: {response.status_code}")

    @task(1)
    def api_me(self):
        """Check de sesión/usuario (bajo peso)."""
        with self.client.get(
            "/api/me/",
            name="GET /api/me",
            catch_response=True,
        ) as response:
            if response.status_code in (200, 401):
                response.success()
            else:
                response.failure(f"status inesperado: {response.status_code}")

    @task(1)
    def auth_login_negative(self):
        """Test negativo: login inválido esperado como 401."""
        with self.client.post(
            "/api/auth/login/",
            json={"username": "noexiste@test.com", "password": "invalid"},
            name="POST /api/auth/login [invalid]",
            catch_response=True,
        ) as response:
            if response.status_code == 401:
                response.success()
            else:
                response.failure(f"status inesperado: {response.status_code}")

    @task(1)
    def jugador_not_found(self):
        """Test negativo: jugador inexistente esperado como 404."""
        with self.client.get(
            "/api/jugador/999999/",
            name="GET /api/jugador/<missing>",
            catch_response=True,
        ) as response:
            if response.status_code == 404:
                response.success()
            else:
                response.failure(f"status inesperado: {response.status_code}")
