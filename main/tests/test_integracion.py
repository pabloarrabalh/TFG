from datetime import date

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from main.models import (
    Calendario,
    ClasificacionJornada,
    Equipo,
    EquipoFavorito,
    Jornada,
    Partido,
    Temporada,
)


class IntegrationClasificacionApiTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.temporada = Temporada.objects.create(nombre="25_26")
        cls.jornada_1 = Jornada.objects.create(temporada=cls.temporada, numero_jornada=1)

        cls.real_madrid = Equipo.objects.create(nombre="Real Madrid")
        cls.barcelona = Equipo.objects.create(nombre="Barcelona")

        ClasificacionJornada.objects.create(
            temporada=cls.temporada,
            jornada=cls.jornada_1,
            equipo=cls.real_madrid,
            posicion=1,
            puntos=3,
            goles_favor=2,
            goles_contra=0,
            diferencia_goles=2,
            partidos_ganados=1,
            partidos_empatados=0,
            partidos_perdidos=0,
        )
        ClasificacionJornada.objects.create(
            temporada=cls.temporada,
            jornada=cls.jornada_1,
            equipo=cls.barcelona,
            posicion=2,
            puntos=0,
            goles_favor=0,
            goles_contra=2,
            diferencia_goles=-2,
            partidos_ganados=0,
            partidos_empatados=0,
            partidos_perdidos=1,
        )

        Calendario.objects.create(
            jornada=cls.jornada_1,
            equipo_local=cls.real_madrid,
            equipo_visitante=cls.barcelona,
            fecha=date(2026, 8, 20),
            match_str="real madrid vs barcelona",
        )

        Partido.objects.create(
            jornada=cls.jornada_1,
            equipo_local=cls.real_madrid,
            equipo_visitante=cls.barcelona,
            goles_local=2,
            goles_visitante=0,
        )

    def test_clasificacion_endpoint_returns_table_and_match_status(self):
        url = reverse("api_clasificacion")
        response = self.client.get(url, {"temporada": "25/26", "jornada": 1})

        self.assertEqual(response.status_code, 200)
        payload = response.json()

        self.assertEqual(payload["jornada_actual"], 1)
        self.assertEqual(len(payload["clasificacion"]), 2)
        self.assertEqual(payload["clasificacion"][0]["equipo"], "Real Madrid")

        self.assertEqual(len(payload["partidos_jornada"]), 1)
        self.assertTrue(payload["partidos_jornada"][0]["jugado"])
        self.assertEqual(payload["partidos_jornada"][0]["goles_local"], 2)

    def test_clasificacion_favoritos_filter_for_logged_user(self):
        user = User.objects.create_user(username="pablo", password="12345678")
        EquipoFavorito.objects.create(usuario=user, equipo=self.real_madrid)

        self.client.force_login(user)

        url = reverse("api_clasificacion")
        response = self.client.get(
            url,
            {"temporada": "25/26", "jornada": 1, "favoritos": "true"},
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()

        self.assertEqual(len(payload["clasificacion"]), 1)
        self.assertEqual(payload["clasificacion"][0]["equipo"], "Real Madrid")
