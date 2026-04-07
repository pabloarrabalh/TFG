from datetime import date, datetime, time
from types import SimpleNamespace
from unittest.mock import patch

from django.contrib.auth.models import User
from django.utils import timezone
from rest_framework.test import APITestCase

from .api_cases_legacy import *  # noqa: F401,F403

from main.models import (
    Amistad,
    Calendario,
    ClasificacionJornada,
    Equipo,
    EquipoFavorito,
    EquipoJugadorTemporada,
    EstadisticasPartidoJugador,
    Jornada,
    Notificacion,
    Partido,
    Plantilla,
    PrediccionJugador,
    SolicitudAmistad,
    Temporada,
    UserProfile,
    Jugador,
)


class UnifiedAPICoverageTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(
            username="tester", email="tester@example.com", password="pass1234"
        )
        cls.friend = User.objects.create_user(
            username="friend", email="friend@example.com", password="pass1234"
        )

        UserProfile.objects.get_or_create(user=cls.user)
        UserProfile.objects.get_or_create(user=cls.friend)

        cls.temp = Temporada.objects.create(nombre="25_26")

        cls.eq1 = Equipo.objects.create(nombre="Real Madrid", estadio="Bernabeu")
        cls.eq2 = Equipo.objects.create(nombre="Barcelona", estadio="Camp Nou")
        cls.eq3 = Equipo.objects.create(nombre="Atletico", estadio="Metropolitano")
        cls.eq4 = Equipo.objects.create(nombre="Valencia", estadio="Mestalla")

        cls.j1 = Jornada.objects.create(temporada=cls.temp, numero_jornada=1)
        cls.j2 = Jornada.objects.create(temporada=cls.temp, numero_jornada=2)
        cls.j3 = Jornada.objects.create(temporada=cls.temp, numero_jornada=3)
        cls.j4 = Jornada.objects.create(temporada=cls.temp, numero_jornada=4)
        cls.j5 = Jornada.objects.create(temporada=cls.temp, numero_jornada=5)

        cls.p1 = Partido.objects.create(
            jornada=cls.j1,
            equipo_local=cls.eq1,
            equipo_visitante=cls.eq2,
            goles_local=2,
            goles_visitante=1,
            estado="JUGADO",
            fecha_partido=timezone.now(),
        )
        cls.p2 = Partido.objects.create(
            jornada=cls.j2,
            equipo_local=cls.eq3,
            equipo_visitante=cls.eq1,
            goles_local=0,
            goles_visitante=0,
            estado="JUGADO",
            fecha_partido=timezone.now(),
        )
        cls.p3 = Partido.objects.create(
            jornada=cls.j3,
            equipo_local=cls.eq2,
            equipo_visitante=cls.eq4,
            goles_local=1,
            goles_visitante=3,
            estado="JUGADO",
            fecha_partido=timezone.now(),
        )

        Calendario.objects.create(
            jornada=cls.j4,
            equipo_local=cls.eq1,
            equipo_visitante=cls.eq3,
            fecha=date.today(),
            hora=time(18, 0),
            match_str="real madrid vs atletico",
        )
        Calendario.objects.create(
            jornada=cls.j4,
            equipo_local=cls.eq2,
            equipo_visitante=cls.eq4,
            fecha=date.today(),
            hora=time(20, 0),
            match_str="barcelona vs valencia",
        )

        cls.jg1 = Jugador.objects.create(nombre="Kepa", apellido="Arrizabalaga", nacionalidad="ES")
        cls.jg2 = Jugador.objects.create(nombre="Ruben", apellido="Dias", nacionalidad="PT")
        cls.jg3 = Jugador.objects.create(nombre="Pedri", apellido="Gonzalez", nacionalidad="ES")
        cls.jg4 = Jugador.objects.create(nombre="Vinicius", apellido="Junior", nacionalidad="BR")

        EquipoJugadorTemporada.objects.create(
            equipo=cls.eq1, jugador=cls.jg1, temporada=cls.temp,
            dorsal=1, edad=29, posicion="Portero", partidos_jugados=3
        )
        EquipoJugadorTemporada.objects.create(
            equipo=cls.eq1, jugador=cls.jg2, temporada=cls.temp,
            dorsal=3, edad=27, posicion="Defensa", partidos_jugados=3
        )
        EquipoJugadorTemporada.objects.create(
            equipo=cls.eq2, jugador=cls.jg3, temporada=cls.temp,
            dorsal=8, edad=22, posicion="Centrocampista", partidos_jugados=3
        )
        EquipoJugadorTemporada.objects.create(
            equipo=cls.eq1, jugador=cls.jg4, temporada=cls.temp,
            dorsal=7, edad=24, posicion="Delantero", partidos_jugados=3
        )

        cls._create_stats(cls.jg1, cls.p1, "Portero", 90, 4)
        cls._create_stats(cls.jg2, cls.p1, "Defensa", 90, 8)
        cls._create_stats(cls.jg3, cls.p1, "Centrocampista", 88, 11)
        cls._create_stats(cls.jg4, cls.p1, "Delantero", 90, 12)

        cls._create_stats(cls.jg1, cls.p2, "Portero", 90, 6)
        cls._create_stats(cls.jg2, cls.p2, "Defensa", 90, 7)
        cls._create_stats(cls.jg3, cls.p2, "Centrocampista", 90, 10)
        cls._create_stats(cls.jg4, cls.p2, "Delantero", 90, 9)

        cls._create_stats(cls.jg3, cls.p3, "Centrocampista", 90, 13)

        ClasificacionJornada.objects.create(
            temporada=cls.temp, jornada=cls.j3, equipo=cls.eq1,
            posicion=1, puntos=7, goles_favor=4, goles_contra=1,
            diferencia_goles=3, partidos_ganados=2, partidos_empatados=1, partidos_perdidos=0
        )
        ClasificacionJornada.objects.create(
            temporada=cls.temp, jornada=cls.j3, equipo=cls.eq2,
            posicion=2, puntos=6, goles_favor=3, goles_contra=2,
            diferencia_goles=1, partidos_ganados=2, partidos_empatados=0, partidos_perdidos=1
        )

        EquipoFavorito.objects.create(usuario=cls.user, equipo=cls.eq1)

        cls.plantilla = Plantilla.objects.create(
            usuario=cls.user,
            nombre="Plantilla 1",
            formacion="4-3-3",
            privacidad="publica",
            predeterminada=True,
            alineacion={
                "Portero": [{"id": cls.jg1.id}],
                "Defensa": [{"id": cls.jg2.id}],
                "Centrocampista": [{"id": cls.jg3.id}],
                "Delantero": [{"id": cls.jg4.id}],
            },
        )

        Notificacion.objects.create(
            usuario=cls.user,
            tipo="solicitud_amistad",
            titulo="Test notif",
            mensaje="Mensaje",
            leida=False,
            datos={"k": "v"},
        )

        PrediccionJugador.objects.create(
            jugador=cls.jg4,
            jornada=cls.j4,
            prediccion=9.5,
            modelo="rf",
        )

    @classmethod
    def _create_stats(cls, jugador, partido, posicion, minutos, puntos):
        EstadisticasPartidoJugador.objects.create(
            partido=partido,
            jugador=jugador,
            min_partido=minutos,
            titular=True,
            gol_partido=1 if posicion == "Delantero" else 0,
            asist_partido=1 if posicion == "Centrocampista" else 0,
            xg_partido=0.8,
            xag=0.3,
            tiros=3,
            tiro_puerta_partido=2,
            pases_totales=35,
            pases_completados_pct=87.0,
            amarillas=1 if posicion == "Defensa" else 0,
            rojas=0,
            goles_en_contra=1 if posicion == "Portero" else 0,
            porcentaje_paradas=72.0 if posicion == "Portero" else 0.0,
            psxg=2.1 if posicion == "Portero" else 0.0,
            puntos_fantasy=puntos,
            entradas=4,
            duelos=8,
            duelos_ganados=5,
            duelos_perdidos=3,
            bloqueos=2,
            despejes=4,
            regates=2,
            regates_completados=1,
            regates_fallidos=1,
            conducciones=7,
            distancia_conduccion=40.0,
            metros_avanzados_conduccion=20.0,
            conducciones_progresivas=3,
            duelos_aereos_ganados=2,
            duelos_aereos_perdidos=1,
            duelos_aereos_ganados_pct=66.6,
            lanzadores_penalties=0,
            lanzadores_corners=1,
            pases_clave=2,
            faltas_cometidas=1,
            faltas_recibidas=2,
            roles=[{"corners": [1, 3]}, {"faltas_recibidas": [1, 2]}],
            posicion=posicion,
            nacionalidad=jugador.nacionalidad,
            edad=24,
        )

    def login(self):
        self.client.force_login(self.user)

    # auth.py
    def test_auth_me_login_logout_register(self):
        res = self.client.get("/api/me/")
        self.assertEqual(res.status_code, 200)

        res = self.client.post(
            "/api/auth/login/",
            {"username": "tester", "password": "pass1234"},
            format="json",
        )
        self.assertEqual(res.status_code, 200)

        res = self.client.post(
            "/api/auth/login/",
            {"username": "tester@example.com", "password": "pass1234"},
            format="json",
        )
        self.assertEqual(res.status_code, 200)

        res = self.client.post(
            "/api/auth/login/",
            {"username": "tester", "password": "wrong"},
            format="json",
        )
        self.assertEqual(res.status_code, 401)

        res = self.client.post("/api/auth/logout/", {}, format="json")
        self.assertEqual(res.status_code, 200)

        res = self.client.post(
            "/api/auth/register/",
            {
                "username": "new_user",
                "email": "new_user@example.com",
                "password1": "pass1234",
                "password2": "pass1234",
            },
            format="json",
        )
        self.assertEqual(res.status_code, 200)

        res = self.client.post(
            "/api/auth/register/",
            {
                "username": "new_user",
                "email": "new_user@example.com",
                "password1": "pass1234",
                "password2": "other",
            },
            format="json",
        )
        self.assertEqual(res.status_code, 400)

    # menu.py
    def test_menu_and_top_jugadores(self):
        res = self.client.get("/api/menu/")
        self.assertEqual(res.status_code, 200)
        self.assertIn("jugadores_destacados_por_posicion", res.data)

        res = self.client.get("/api/menu/?jornada=3")
        self.assertEqual(res.status_code, 200)

        res = self.client.get("/api/menu/top-jugadores/?jornada=4")
        self.assertEqual(res.status_code, 200)

        res = self.client.get("/api/menu/top-jugadores/?jornada=bad")
        self.assertEqual(res.status_code, 400)

    # clasificacion.py
    def test_clasificacion_filters(self):
        self.login()
        res = self.client.get("/api/clasificacion/?temporada=25/26")
        self.assertEqual(res.status_code, 200)

        res = self.client.get("/api/clasificacion/?temporada=25/26&jornada=3")
        self.assertEqual(res.status_code, 200)

        res = self.client.get("/api/clasificacion/?temporada=25/26&equipo=Real Madrid")
        self.assertEqual(res.status_code, 200)

        res = self.client.get("/api/clasificacion/?temporada=25/26&favoritos=true")
        self.assertEqual(res.status_code, 200)

    # equipo.py
    def test_equipos_y_equipo_detalle(self):
        self.login()
        res = self.client.get("/api/equipos/")
        self.assertEqual(res.status_code, 200)
        self.assertIn("equipos", res.data)

        res = self.client.get("/api/equipo/Real Madrid/?temporada=25/26&jornada=3")
        self.assertEqual(res.status_code, 200)
        self.assertIn("jugadores", res.data)

        res = self.client.get("/api/equipo/NoExiste/")
        self.assertEqual(res.status_code, 404)

    # jugador.py
    def test_jugador_detail_y_top_posicion(self):
        res = self.client.get(f"/api/jugador/{self.jg4.id}/?temporada=25/26")
        self.assertEqual(res.status_code, 200)
        self.assertIn("stats", res.data)

        res = self.client.get(f"/api/jugador/{self.jg4.id}/?temporada=carrera")
        self.assertEqual(res.status_code, 200)

        res = self.client.get("/api/top-jugadores-por-posicion/?temporada=25/26")
        self.assertEqual(res.status_code, 200)

        from main.api import jugador as jugador_mod

        self.assertEqual(jugador_mod._safe_float(float("nan"), default=7), 7)
        self.assertEqual(jugador_mod._safe_float(float("inf"), default=8), 8)
        self.assertEqual(jugador_mod._safe_float(2.5, default=0), 2.5)

        clean = jugador_mod._sanitize_dict({"a": float("nan"), "b": {"c": float("inf")}}, default=0)
        self.assertEqual(clean["a"], 0)
        self.assertEqual(clean["b"]["c"], 0)

        pred_rows = jugador_mod._get_datos_temporada_completa(self.jg4, self.temp)
        self.assertGreaterEqual(len(pred_rows), 1)

        hist_rows = jugador_mod._get_ultimos_8_temporada_completa(self.jg4, self.temp)
        self.assertGreaterEqual(len(hist_rows), 1)

        merged_preds = jugador_mod._get_predicciones_jugador(self.jg4, self.temp)
        self.assertGreaterEqual(len(merged_preds), 1)

    # jugador_partidos.py + jugador_insight.py
    def test_jugador_partidos_and_insight(self):
        res = self.client.get(f"/api/jugador-partidos/?jugador_id={self.jg4.id}&jornada_actual=3")
        self.assertEqual(res.status_code, 200)
        self.assertIn("partidos", res.data)

        res = self.client.get("/api/jugador-partidos/?jugador_id=&jornada_actual=")
        self.assertEqual(res.status_code, 200)

        res = self.client.get(f"/api/jugador-insight/?jugador_id={self.jg4.id}&temporada=25/26&jornada=3")
        self.assertEqual(res.status_code, 200)

        from main.api import jugador_insight as ji

        self.assertGreaterEqual(ji._xg_ratio({"goles": 2, "xg": 1}), 1)
        self.assertGreaterEqual(ji._pct_duelos({"duelos_totales": 10, "duelos_ganados": 7}), 0.6)
        self.assertGreaterEqual(
            ji._pct_duelos_aereos({"duelos_aereos_totales": 10, "duelos_aereos_ganados": 7}), 0.6
        )

        insights = ji.get_insights(
            {
                "goles": 5,
                "xg": 3.0,
                "asistencias": 4,
                "xag": 2.0,
                "partidos": 10,
                "promedio_puntos": 5.5,
                "duelos_totales": 12,
                "duelos_ganados": 8,
                "duelos_aereos_totales": 22,
                "duelos_aereos_ganados": 14,
                "despejes": 12,
                "entradas": 11,
                "regates_completados": 12,
                "conducciones_progresivas": 24,
                "amarillas": 4,
                "minutos": 1500,
                "porcentaje_paradas": 70,
                "goles_en_contra": 8,
                "tiros_contra": 60,
                "psxg_total": 11,
                "pases_accuracy": 88,
                "pases_totales": 150,
            },
            "Defensa",
            n=3,
        )
        self.assertGreaterEqual(len(insights), 1)

    # buscar.py
    def test_buscar_and_radar(self):
        res = self.client.get(f"/api/radar/{self.jg4.id}/25_26/")
        self.assertEqual(res.status_code, 200)

        res = self.client.get("/api/buscar/?q=a")
        self.assertEqual(res.status_code, 400)

        with patch("main.api.buscar.OPENSEARCH_AVAILABLE", False):
            res = self.client.get("/api/buscar/?q=vin")
            self.assertEqual(res.status_code, 503)

        fake_hits_j = {
            "hits": {
                "hits": [
                    {
                        "_source": {
                            "id": self.jg4.id,
                            "nombre": self.jg4.nombre,
                            "apellido": self.jg4.apellido,
                            "posicion": "Delantero",
                        }
                    }
                ]
            }
        }
        fake_hits_e = {
            "hits": {
                "hits": [
                    {"_source": {"id": self.eq1.id, "nombre": self.eq1.nombre, "estadio": self.eq1.estadio}}
                ]
            }
        }
        fake_client = SimpleNamespace(search=lambda index, body: fake_hits_j if index == "jugadores" else fake_hits_e)

        with patch("main.api.buscar.OPENSEARCH_AVAILABLE", True), patch("main.api.buscar.opensearch_client", fake_client):
            res = self.client.get("/api/buscar/?q=vin")
            self.assertEqual(res.status_code, 200)
            self.assertIn("results", res.data)

    # perfil.py
    def test_perfil_endpoints(self):
        self.login()

        res = self.client.get("/api/perfil/")
        self.assertEqual(res.status_code, 200)

        res = self.client.patch("/api/perfil/update/", {"nickname": "nick1"}, format="json")
        self.assertEqual(res.status_code, 200)

        res = self.client.patch("/api/perfil/status/", {"estado": "active"}, format="json")
        self.assertEqual(res.status_code, 200)

        res = self.client.patch("/api/perfil/status/", {"estado": "invalid"}, format="json")
        self.assertEqual(res.status_code, 400)

        res = self.client.patch(
            "/api/perfil/preferencias-notificaciones/",
            {"preferencias_notificaciones": "friends"},
            format="json",
        )
        self.assertEqual(res.status_code, 200)

        res = self.client.post("/api/perfil/cambiar-jornada/", {"jornada": 3}, format="json")
        self.assertEqual(res.status_code, 200)

        res = self.client.post("/api/perfil/cambiar-jornada/", {"jornada": "bad"}, format="json")
        self.assertEqual(res.status_code, 400)

        res = self.client.post("/api/perfil/foto/", {}, format="multipart")
        self.assertEqual(res.status_code, 400)

    def test_perfil_upload_default_avatar_success(self):
        import os
        from django.conf import settings

        self.login()

        logos_dir = os.path.join(settings.BASE_DIR, "static", "logos")
        os.makedirs(logos_dir, exist_ok=True)
        avatar_path = os.path.join(logos_dir, "test_avatar_cov.png")
        with open(avatar_path, "wb") as f:
            f.write(b"\x89PNG\r\n\x1a\n")

        res = self.client.post(
            "/api/perfil/foto/",
            {"default_avatar": "test_avatar_cov"},
            format="multipart",
        )
        self.assertEqual(res.status_code, 200)

        res = self.client.post(
            "/api/perfil/foto/",
            {"shield_team": "Equipo Invalido"},
            format="multipart",
        )
        self.assertEqual(res.status_code, 400)

    # favoritos.py
    def test_favoritos_endpoints(self):
        res = self.client.get("/api/favoritos/")
        self.assertEqual(res.status_code, 200)

        self.login()
        res = self.client.get("/api/favoritos/")
        self.assertEqual(res.status_code, 200)

        res = self.client.post("/api/favoritos/toggle-v2/", {"equipo_id": self.eq2.id}, format="json")
        self.assertEqual(res.status_code, 200)

        res = self.client.post("/api/favoritos/toggle-v2/", {"equipo_id": self.eq2.id}, format="json")
        self.assertEqual(res.status_code, 200)

        fav = EquipoFavorito.objects.filter(usuario=self.user).first()
        if fav:
            res = self.client.delete(f"/api/favoritos/{fav.id}/")
            self.assertIn(res.status_code, [200, 404])

    # amigos.py
    def test_amigos_endpoints(self):
        self.login()

        res = self.client.get("/api/amigos/")
        self.assertEqual(res.status_code, 200)

        res = self.client.post("/api/amigos/solicitud/", {"username": "friend"}, format="json")
        self.assertEqual(res.status_code, 200)

        sol = SolicitudAmistad.objects.filter(emisor=self.user, receptor=self.friend).first()
        self.assertIsNotNone(sol)

        self.client.force_login(self.friend)
        res = self.client.post(f"/api/amigos/aceptar/{sol.id}/", {}, format="json")
        self.assertEqual(res.status_code, 200)

        self.client.force_login(self.user)
        res = self.client.get(f"/api/amigos/{self.friend.id}/plantillas/")
        self.assertIn(res.status_code, [200, 403])

        res = self.client.post(f"/api/amigos/eliminar/{self.friend.id}/", {}, format="json")
        self.assertEqual(res.status_code, 200)

        SolicitudAmistad.objects.create(emisor=self.friend, receptor=self.user, estado="pendiente")
        sol2 = SolicitudAmistad.objects.filter(emisor=self.friend, receptor=self.user, estado="pendiente").first()
        res = self.client.post(f"/api/amigos/rechazar/{sol2.id}/", {}, format="json")
        self.assertEqual(res.status_code, 200)

    def test_amigos_negative_paths(self):
        self.login()

        res = self.client.post("/api/amigos/solicitud/", {"username": "tester"}, format="json")
        self.assertEqual(res.status_code, 400)

        res = self.client.post("/api/amigos/solicitud/", {"username": "usuario_no_existe"}, format="json")
        self.assertEqual(res.status_code, 404)

        res = self.client.post("/api/amigos/solicitud/", {"username": "friend"}, format="json")
        self.assertEqual(res.status_code, 200)

        res = self.client.post("/api/amigos/solicitud/", {"username": "friend"}, format="json")
        self.assertEqual(res.status_code, 400)

        res = self.client.post("/api/amigos/aceptar/999999/", {}, format="json")
        self.assertEqual(res.status_code, 400)

        res = self.client.post("/api/amigos/rechazar/999999/", {}, format="json")
        self.assertEqual(res.status_code, 400)

        res = self.client.get(f"/api/amigos/999999/plantillas/")
        self.assertEqual(res.status_code, 404)

    # plantilla.py
    def test_plantilla_endpoints(self):
        self.login()

        res = self.client.get("/api/mi-plantilla/?temporada=25/26&jornada=3")
        self.assertEqual(res.status_code, 200)

        res = self.client.get("/api/mi-plantilla/jugadores/?pos=Defensa&q=Ruben&temporada=25/26")
        self.assertEqual(res.status_code, 200)

        res = self.client.get("/api/plantillas/usuario/")
        self.assertEqual(res.status_code, 200)

        res = self.client.post(
            "/api/plantillas/usuario/",
            {"nombre": "Plantilla 2", "formacion": "4-4-2", "alineacion": {}},
            format="json",
        )
        self.assertEqual(res.status_code, 200)
        pid = res.data["plantilla_id"]

        res = self.client.post(f"/api/plantillas/usuario/{pid}/renombrar/", {"nombre": "Renombrada"}, format="json")
        self.assertEqual(res.status_code, 200)

        res = self.client.post(f"/api/plantilla/{pid}/privacidad/", {}, format="json")
        self.assertEqual(res.status_code, 200)

        res = self.client.post(f"/api/plantilla/{pid}/predeterminada/", {}, format="json")
        self.assertEqual(res.status_code, 200)

        res = self.client.get("/api/plantillas/privacidad/")
        self.assertEqual(res.status_code, 200)

        res = self.client.delete(f"/api/plantillas/usuario/{pid}/")
        self.assertEqual(res.status_code, 200)

    # plantilla_notificaciones.py + notificaciones.py
    def test_plantilla_notificaciones_and_notificaciones(self):
        self.login()

        res = self.client.get("/api/plantilla-notificaciones/1/")
        self.assertEqual(res.status_code, 200)
        self.assertIn("eventos", res.data)

        res = self.client.get("/api/notificaciones/")
        self.assertEqual(res.status_code, 200)

        notif = Notificacion.objects.filter(usuario=self.user).first()
        self.assertIsNotNone(notif)

        res = self.client.post(f"/api/notificaciones/{notif.id}/leer/", {}, format="json")
        self.assertEqual(res.status_code, 200)

        res = self.client.post("/api/notificaciones/leer-todas/", {}, format="json")
        self.assertEqual(res.status_code, 200)

        res = self.client.post(f"/api/notificaciones/{notif.id}/borrar/", {}, format="json")
        self.assertEqual(res.status_code, 200)

        res = self.client.post("/api/notificaciones/borrar-todas/", {}, format="json")
        self.assertEqual(res.status_code, 200)

    # estadisticas.py
    def test_estadisticas_and_comparacion(self):
        res = self.client.get("/api/estadisticas/?temporada=25_26")
        self.assertEqual(res.status_code, 200)
        self.assertIn("estadisticas", res.data)

        res = self.client.get("/api/estadisticas/?temporada=25_26&tipo=goles&limit=10&offset=0")
        self.assertEqual(res.status_code, 200)

        res = self.client.get("/api/estadisticas/?temporada=25_26&jornada=1")
        self.assertEqual(res.status_code, 200)

        res = self.client.get("/api/estadisticas/?temporada=25_26&jornada_desde=1&jornada_hasta=3")
        self.assertEqual(res.status_code, 200)

        res = self.client.get("/api/estadisticas/?temporada=25_26&search=vin")
        self.assertEqual(res.status_code, 200)

        res = self.client.get(
            f"/api/estadisticas/comparacion/?jugador_ids={self.jg3.id},{self.jg4.id}&temporada=25_26"
        )
        self.assertEqual(res.status_code, 200)

        from main.api.estadisticas import calcular_puntos_fantasy_filtrados_lista

        self.assertEqual(calcular_puntos_fantasy_filtrados_lista([]), 0)
        self.assertEqual(calcular_puntos_fantasy_filtrados_lista([50, 60]), 0)
        self.assertGreaterEqual(calcular_puntos_fantasy_filtrados_lista([10, 45, 12]), 20)

    # predicciones.py
    def test_predicciones_endpoints(self):
        predecir_mod = SimpleNamespace(
            predecir_puntos_portero=lambda nombre, jornada, verbose=False, modelo_tipo="RF": {
                "prediccion": 7.25,
                "puntos_reales": 6.0,
                "puntos_reales_texto": "ok",
                "margen": 1.0,
                "rango_min": 6.0,
                "rango_max": 8.0,
                "jornada": jornada or 4,
                "modelo": "Random Forest",
            },
            predecir_puntos=lambda jugador_id, pos, jornada_actual=None, verbose=False, modelo_tipo=None: {
                "prediccion": 8.4,
                "jornada": jornada_actual or 4,
            },
        )

        with patch.dict("sys.modules", {"predecir": predecir_mod}):
            res = self.client.post(
                "/api/predecir-portero/",
                {"jugador_id": self.jg1.id, "jornada": 4, "modelo": "RF"},
                format="json",
            )
            self.assertEqual(res.status_code, 200)

            res = self.client.post(
                "/api/explicar-prediccion/",
                {"jugador_id": self.jg4.id, "jornada": 4, "posicion": "DT", "modelo": "RF"},
                format="json",
            )
            self.assertEqual(res.status_code, 200)

        res = self.client.post(
            "/api/predecir-jugador/",
            {"jugador_id": self.jg4.id, "jornada": 4, "posicion": "DT", "modelo": "rf"},
            format="json",
        )
        self.assertEqual(res.status_code, 200)

        res = self.client.post(
            "/api/cambiar-jornada/",
            {"jornada": 4},
            format="json",
        )
        self.assertEqual(res.status_code, 200)

        res = self.client.post(
            "/api/predecir-jugador/",
            {"jugador_id": self.jg4.id, "jornada": 2, "posicion": "DT", "modelo": "rf"},
            format="json",
        )
        self.assertEqual(res.status_code, 200)

        res = self.client.post(
            "/api/predecir-portero/",
            {"jornada": 4},
            format="json",
        )
        self.assertEqual(res.status_code, 400)

    # consejero.py
    def test_consejero_endpoint_and_helpers(self):
        self.login()

        with patch("main.api.consejero._cargar_modelo", return_value=False):
            res = self.client.post(
                "/api/consejero/",
                {"jugador_id": self.jg4.id, "accion": "fichar"},
                format="json",
            )
            self.assertEqual(res.status_code, 200)
            self.assertIn("veredicto", res.data)

        from main.api import consejero as cons

        stats = list(
            EstadisticasPartidoJugador.objects.filter(jugador=self.jg4).order_by("-partido__jornada__numero_jornada")
        )
        features = cons._computar_features(stats, "DT", 8.2, 6.5, self.temp)
        self.assertEqual(features.shape[1], 7)

        veredicto, razon = cons._fallback_veredicto(self.jg4, "mantener", 8.0, 6.5, 1.5, 3, 270)
        self.assertTrue(veredicto)
        self.assertTrue(razon)

    def test_consejero_ml_branches(self):
        import numpy as np
        from main.api import consejero as cons

        class _Scaler:
            def transform(self, arr):
                return arr

        class _Clf:
            def predict_proba(self, arr):
                return np.array([[0.2, 0.3, 0.5]])

        class _Pipeline:
            named_steps = {"scaler": _Scaler(), "clf": _Clf()}

        class _Explainer:
            def shap_values(self, arr):
                return [
                    np.array([[0.1] * 7]),
                    np.array([[0.2] * 7]),
                    np.array([[0.3, 0.1, 0.05, -0.2, 0.4, 0.12, 0.01]]),
                ]

        cons._pipeline = _Pipeline()
        cons._explainer = _Explainer()

        rec, conf, factors = cons._predecir(np.array([[1, 2, 3, 0.5, 1.0, 0.8, 3]]))
        self.assertIn(rec, ["vender", "mantener", "fichar"])
        self.assertGreaterEqual(conf, 0)
        self.assertIsInstance(factors, list)

        for accion in ["fichar", "vender", "mantener"]:
            for recomendacion in ["fichar", "vender", "mantener"]:
                v, r = cons._generar_veredicto_ml(
                    self.jg4,
                    accion,
                    recomendacion,
                    77,
                    factors,
                    7.9,
                    6.1,
                    1.8,
                    2,
                    190,
                )
                self.assertTrue(v)
                self.assertTrue(r)

        media = cons._obtener_media_posicion("Delantero", self.temp)
        self.assertIsNotNone(media)

    def test_clasificacion_helpers_and_paths(self):
        from main.api.clasificacion import ClasificacionView

        res = self.client.get("/api/clasificacion/?temporada=25/26&jornada=bad")
        self.assertEqual(res.status_code, 200)

        res = self.client.get("/api/clasificacion/?temporada=00/00")
        self.assertEqual(res.status_code, 200)

        vacio = ClasificacionView._empty_sucesos()
        self.assertIn("goles_local", vacio)

        sucesos = ClasificacionView._build_sucesos(self.p1, self.temp)
        self.assertIn("goles_local", sucesos)

    def test_menu_internal_branches(self):
        from main.api import menu as menu_mod

        cal = Calendario.objects.filter(jornada=self.j4).first()
        data = menu_mod._serialize_partido_calendario(cal)
        self.assertIn("equipo_local", data)

        no_data = menu_mod._get_jugadores_destacados_con_predicciones(None, None)
        self.assertEqual(no_data, {})

        yes_data = menu_mod._get_jugadores_destacados_con_predicciones(self.temp, self.j4)
        self.assertIsInstance(yes_data, dict)

        fake_predecir = SimpleNamespace(
            predecir_puntos=lambda jugador_id, pos_code, jornada_num, verbose=False: {
                "prediccion": 7.2,
            }
        )
        with patch("main.api.menu.importlib.import_module", return_value=fake_predecir):
            menu_mod._bg_compute_predictions(self.temp.id, self.j4.numero_jornada, "test_cache_key_cov")

    # smoke for api/v2 and method edges
    def test_api_v2_and_method_edges(self):
        res = self.client.get("/api/v2/jugadores/")
        self.assertIn(res.status_code, [200, 401, 403])

        res = self.client.get("/api/v2/equipos/")
        self.assertIn(res.status_code, [200, 401, 403])

        res = self.client.get("/api/v2/clasificacion/")
        self.assertIn(res.status_code, [200, 401, 403])

        res = self.client.get("/api/v2/jornadas/")
        self.assertIn(res.status_code, [200, 401, 403])

        res = self.client.post("/api/equipos/", {}, format="json")
        self.assertIn(res.status_code, [405, 400, 403])
