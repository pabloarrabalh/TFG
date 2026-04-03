from django.test import SimpleTestCase

from main.scrapping.matching import agrupar_propuestas_por_norm, resolver_matching


class MatchingAssignmentTests(SimpleTestCase):
    def test_resolver_matching_assigns_high_points_to_player_with_more_minutes(self):
        propuestas = [
            {
                "clave_fbref": "fbref_a",
                "nombre_fb": "Jugador A",
                "nombre_fb_norm": "jugador a",
                "equipo_fb_norm": "girona",
                "minutos": 90,
                "posicion": "MC",
                "mejor_norm": "jose perez",
                "mejor_original": "Jose Perez",
                "score": 95.0,
            },
            {
                "clave_fbref": "fbref_b",
                "nombre_fb": "Jugador B",
                "nombre_fb_norm": "jugador b",
                "equipo_fb_norm": "girona",
                "minutos": 45,
                "posicion": "MC",
                "mejor_norm": "jose perez",
                "mejor_original": "Jose Perez",
                "score": 90.0,
            },
        ]

        jugadores_por_apellido_equipo = {
            ("perez", "girona"): [
                ("ff_1", {"nombre_norm": "jose perez"}),
            ],
        }

        fantasy_por_norm = {
            ("jose perez", "girona"): [
                {
                    "clave_ff": "ff_top",
                    "puntos": 10,
                    "info": {
                        "nombre_norm": "jose perez",
                        "nombre_original": "Jose Perez",
                    },
                },
                {
                    "clave_ff": "ff_low",
                    "puntos": 4,
                    "info": {
                        "nombre_norm": "jose perez",
                        "nombre_original": "Jose Perez",
                    },
                },
            ]
        }

        asignacion, debug = resolver_matching(
            propuestas,
            jugadores_por_apellido_equipo,
            fantasy_por_norm,
        )

        self.assertEqual(asignacion["fbref_a"], "ff_top")
        self.assertEqual(asignacion["fbref_b"], "ff_low")
        self.assertEqual(debug["fbref_a"]["clave_ff_asignada"], "ff_top")
        self.assertEqual(debug["fbref_b"]["clave_ff_asignada"], "ff_low")

    def test_resolver_matching_single_candidate_chooses_best_score(self):
        propuestas = [
            {
                "clave_fbref": "fbref_low_score",
                "nombre_fb": "J. Perez",
                "nombre_fb_norm": "j perez",
                "equipo_fb_norm": "girona",
                "minutos": 60,
                "posicion": "MC",
                "mejor_norm": "jose perez",
                "mejor_original": "Jose Perez",
                "score": 80.0,
            },
            {
                "clave_fbref": "fbref_best_score",
                "nombre_fb": "Jose Perez",
                "nombre_fb_norm": "jose perez",
                "equipo_fb_norm": "girona",
                "minutos": 20,
                "posicion": "MC",
                "mejor_norm": "jose perez",
                "mejor_original": "Jose Perez",
                "score": 97.0,
            },
        ]

        jugadores_por_apellido_equipo = {
            ("perez", "girona"): [
                ("ff_only", {"nombre_norm": "jose perez"}),
            ],
        }

        fantasy_por_norm = {
            ("jose perez", "girona"): [
                {
                    "clave_ff": "ff_only",
                    "puntos": 8,
                    "info": {
                        "nombre_norm": "jose perez",
                        "nombre_original": "Jose Perez",
                    },
                }
            ]
        }

        asignacion, _ = resolver_matching(
            propuestas,
            jugadores_por_apellido_equipo,
            fantasy_por_norm,
        )

        self.assertEqual(asignacion["fbref_best_score"], "ff_only")
        self.assertNotIn("fbref_low_score", asignacion)

    def test_resolver_matching_without_fantasy_candidates_leaves_unassigned(self):
        propuestas = [
            {
                "clave_fbref": "fbref_sin_destino",
                "nombre_fb": "Jugador X",
                "nombre_fb_norm": "jugador x",
                "equipo_fb_norm": "girona",
                "minutos": 70,
                "posicion": "MC",
                "mejor_norm": "jose perez",
                "mejor_original": "Jose Perez",
                "score": 92.0,
            }
        ]

        jugadores_por_apellido_equipo = {
            ("perez", "girona"): [("ff_1", {"nombre_norm": "jose perez"})]
        }

        asignacion, debug = resolver_matching(
            propuestas,
            jugadores_por_apellido_equipo,
            fantasy_por_norm={},
        )

        self.assertEqual(asignacion, {})
        self.assertIsNone(debug["fbref_sin_destino"]["clave_ff_asignada"])

    def test_agrupar_propuestas_skips_low_score_when_surname_not_unique(self):
        propuestas = [
            {
                "clave_fbref": "fbref_low",
                "nombre_fb": "J. Rodriguez",
                "nombre_fb_norm": "j rodriguez",
                "equipo_fb_norm": "sevilla",
                "minutos": 20,
                "posicion": "MC",
                "mejor_norm": "rodriguez",
                "mejor_original": "Rodriguez",
                "score": 10.0,
            }
        ]

        jugadores_por_apellido_equipo = {
            ("rodriguez", "sevilla"): [
                ("ff_a", {"nombre_norm": "m rodriguez"}),
                ("ff_b", {"nombre_norm": "j rodriguez"}),
            ]
        }

        agrupadas = agrupar_propuestas_por_norm(propuestas, jugadores_por_apellido_equipo)
        self.assertEqual(agrupadas, {})
