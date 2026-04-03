from django.core.exceptions import ValidationError
from django.test import TestCase

from main.models import (
    Equipo,
    EstadisticasPartidoJugador,
    Jornada,
    Jugador,
    Partido,
    Posicion,
    Temporada,
)


class UnitModelTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.temporada = Temporada.objects.create(nombre="25_26")
        cls.jornada_1 = Jornada.objects.create(temporada=cls.temporada, numero_jornada=1)
        cls.jornada_2 = Jornada.objects.create(temporada=cls.temporada, numero_jornada=2)

        cls.real_madrid = Equipo.objects.create(nombre="Real Madrid")
        cls.barcelona = Equipo.objects.create(nombre="Barcelona")

        cls.partido_1 = Partido.objects.create(
            jornada=cls.jornada_1,
            equipo_local=cls.real_madrid,
            equipo_visitante=cls.barcelona,
        )
        cls.partido_2 = Partido.objects.create(
            jornada=cls.jornada_2,
            equipo_local=cls.barcelona,
            equipo_visitante=cls.real_madrid,
        )

    def test_partido_clean_rejects_same_local_and_away_team(self):
        partido_invalido = Partido(
            jornada=self.jornada_1,
            equipo_local=self.real_madrid,
            equipo_visitante=self.real_madrid,
        )

        with self.assertRaises(ValidationError):
            partido_invalido.full_clean()

    def test_get_posicion_mas_frecuente_returns_none_without_stats(self):
        jugador = Jugador.objects.create(
            nombre="Luka",
            apellido="Modric",
            nacionalidad="Croacia",
        )

        self.assertIsNone(jugador.get_posicion_mas_frecuente())

    def test_get_posicion_mas_frecuente_returns_most_common_position(self):
        jugador = Jugador.objects.create(
            nombre="Fede",
            apellido="Valverde",
            nacionalidad="Uruguay",
        )

        # bulk_create evita disparar señales post_save y mantiene el test rápido.
        EstadisticasPartidoJugador.objects.bulk_create(
            [
                EstadisticasPartidoJugador(
                    partido=self.partido_1,
                    jugador=jugador,
                    posicion=Posicion.CENTROCAMPISTA,
                    min_partido=90,
                ),
                EstadisticasPartidoJugador(
                    partido=self.partido_2,
                    jugador=jugador,
                    posicion=Posicion.CENTROCAMPISTA,
                    min_partido=85,
                ),
            ]
        )

        self.assertEqual(
            jugador.get_posicion_mas_frecuente(),
            Posicion.CENTROCAMPISTA,
        )
