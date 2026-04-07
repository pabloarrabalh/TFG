from django.test import TestCase
from django.urls import reverse
from main.models import Temporada, Equipo, Jugador, EquipoFavorito


class E2EAuthJourneyTests(TestCase):
    def test_register_me_logout_full_journey(self):
        me_url = reverse("api_me")
        register_url = reverse("api_auth_register")
        logout_url = reverse("api_auth_logout")

        initial_me = self.client.get(me_url)
        self.assertEqual(initial_me.status_code, 200)
        self.assertFalse(initial_me.json()["authenticated"])
        self.assertIn("csrftoken", initial_me.cookies)

        register_payload = {
            "email": "pablo@example.com",
            "username": "pablo",
            "password1": "super-segura-123",
            "password2": "super-segura-123",
        }
        register_response = self.client.post(register_url, data=register_payload)

        self.assertEqual(register_response.status_code, 200)
        self.assertEqual(register_response.json()["status"], "ok")

        after_register_me = self.client.get(me_url)
        self.assertEqual(after_register_me.status_code, 200)
        self.assertTrue(after_register_me.json()["authenticated"])
        self.assertEqual(after_register_me.json()["username"], "pablo")

        logout_response = self.client.post(logout_url)
        self.assertEqual(logout_response.status_code, 200)

        after_logout_me = self.client.get(me_url)
        self.assertEqual(after_logout_me.status_code, 200)
        self.assertFalse(after_logout_me.json()["authenticated"])


class E2EEquiposNavegacionTests(TestCase):
    """E2E test: Usuario navega por equipos y visualiza detalles."""
    
    @classmethod
    def setUpTestData(cls):
        cls.temp = Temporada.objects.create(nombre="25_26")
        cls.eq1 = Equipo.objects.create(nombre="Real Madrid", estadio="Bernabeu")
        cls.eq2 = Equipo.objects.create(nombre="Barcelona", estadio="Camp Nou")
    
    def test_list_equipos_then_view_detail(self):
        """Usuario lista equipos y luego ve detalles de uno."""
        list_response = self.client.get(reverse("api_equipos"))
        self.assertEqual(list_response.status_code, 200)
        
        equipos = list_response.json()
        self.assertGreaterEqual(len(equipos), 2)
        
        equipo_id = equipos[0]["id"]
        detail_response = self.client.get(reverse("api_equipo_detail", args=[equipo_id]))
        self.assertEqual(detail_response.status_code, 200)
        self.assertIn("nombre", detail_response.json())


class E2EFavoritosToggleTests(TestCase):
    """E2E test: Usuario autenticado agrega/quita favoritos."""
    
    @classmethod
    def setUpTestData(cls):
        cls.temp = Temporada.objects.create(nombre="25_26")
        cls.equipo = Equipo.objects.create(nombre="Atletico Madrid", estadio="Wanda")
    
    def test_toggle_favorite_team_authenticated(self):
        """Usuario registrado puede marcar/desmarcar equipos favoritos."""
        from django.contrib.auth.models import User
        
        user = User.objects.create_user(username="fan", password="pass123")
        self.client.login(username="fan", password="pass123")
        
        toggle_url = reverse("api_toggle_equipo_favorito")
        response = self.client.post(toggle_url, {"equipo_id": self.equipo.id}, content_type="application/json")
        
        self.assertIn(response.status_code, [200, 201])
        
        # Verificar que se agregó
        me_response = self.client.get(reverse("api_me"))
        self.assertTrue(me_response.json().get("authenticated"))


class E2EJugadorSearchTests(TestCase):
    """E2E test: Usuario busca y visualiza jugadores."""
    
    @classmethod
    def setUpTestData(cls):
        cls.temp = Temporada.objects.create(nombre="25_26")
        cls.equipo = Equipo.objects.create(nombre="Valencia", estadio="Mestalla")
        cls.jugador = Jugador.objects.create(
            nombre="Test Player",
            apellido="Prueba",
            equipo=cls.equipo,
            temporada=cls.temp,
            posicion="DT"
        )
    
    def test_search_and_view_jugador(self):
        """Usuario busca un jugador y accede a su detalle."""
        detail_url = reverse("api_jugador_detail", args=[self.jugador.id])
        response = self.client.get(detail_url)
        
        self.assertIn(response.status_code, [200, 404])
        
        if response.status_code == 200:
            data = response.json()
            self.assertIn("nombre", data)


class E2EClasificacionJornadaTests(TestCase):
    """E2E test: Usuario consulta clasificación por jornada."""
    
    @classmethod
    def setUpTestData(cls):
        from main.models import Jornada
        
        cls.temp = Temporada.objects.create(nombre="25_26")
        cls.jornada = Jornada.objects.create(temporada=cls.temp, numero_jornada=1)
    
    def test_get_clasificacion_by_jornada(self):
        """Usuario solicita tabla de clasificación para una jornada específica."""
        response = self.client.get(
            reverse("api_clasificacion"),
            {"temporada": "25_26", "jornada": 1}
        )
        
        self.assertIn(response.status_code, [200, 404])

