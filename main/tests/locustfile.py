import random

from locust import HttpUser, between, task


class LigaMasterApiUser(HttpUser):
    """Carga de APIs públicas en modo lectura para validar latencia y estabilidad."""

    wait_time = between(0.3, 1.5)
    jornadas = (1, 5, 10, 15, 20, 25, 30)

    def on_start(self):
        # Inicializa sesión/cookies del cliente al arrancar cada usuario virtual.
        self.client.get("/api/me/", name="GET /api/me [bootstrap]")

    @task(4)
    def me(self):
        with self.client.get("/api/me/", name="GET /api/me", catch_response=True) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"status inesperado: {response.status_code}")

    @task(4)
    def equipos(self):
        with self.client.get("/api/equipos/", name="GET /api/equipos", catch_response=True) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"status inesperado: {response.status_code}")

    @task(3)
    def clasificacion(self):
        jornada = random.choice(self.jornadas)
        with self.client.get(
            "/api/clasificacion/",
            params={"temporada": "25/26", "jornada": jornada},
            name="GET /api/clasificacion",
            catch_response=True,
        ) as response:
            if response.status_code in (200, 404):
                response.success()
            else:
                response.failure(f"status inesperado: {response.status_code}")

    @task(2)
    def health(self):
        with self.client.get("/health/", name="GET /health", catch_response=True) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"status inesperado: {response.status_code}")

    @task(2)
    def jugador_detail_missing(self):
        # Test negativo de API: id inexistente debe responder 404.
        with self.client.get("/api/jugador/999999/", name="GET /api/jugador/<missing>", catch_response=True) as response:
            if response.status_code == 404:
                response.success()
            else:
                response.failure(f"status inesperado: {response.status_code}")

    @task(1)
    def auth_login_negative(self):
        # Test negativo de API: login inválido esperado como 401.
        with self.client.post(
            "/api/auth/login/",
            json={"username": "noexiste", "password": "bad-pass"},
            name="POST /api/auth/login [invalid]",
            catch_response=True,
        ) as response:
            if response.status_code == 401:
                response.success()
            else:
                response.failure(f"status inesperado: {response.status_code}")
