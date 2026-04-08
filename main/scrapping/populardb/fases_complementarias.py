import logging
import os

import pandas as pd
from django.conf import settings
from django.db.models import Max, Sum

from main.models import (
    ClasificacionJornada,
    Equipo,
    EquipoJugadorTemporada,
    EstadisticasPartidoJugador,
    Jornada,
    RendimientoHistoricoJugador,
    Temporada,
)
from main.scrapping.commons import normalizar_equipo_bd, normalizar_texto
from main.scrapping.roles import ROLES_DESTACADOS


def fase_2_cargar_roles():
    """FASE 2: Carga roles desde ROLES_DESTACADOS de roles.py (optimizado)."""
    _log = logging.getLogger(__name__)
    _log.info("[FASE 2] Cargando roles...")

    if not ROLES_DESTACADOS:
        return

    try:
        temporadas_map = {
            "23_24": Temporada.objects.get(nombre="23_24"),
            "24_25": Temporada.objects.get(nombre="24_25"),
            "25_26": Temporada.objects.get(nombre="25_26"),
        }
    except Temporada.DoesNotExist as e:
        _log.warning("Temporada no encontrada en roles: %s", e)
        return

    contador_total = 0

    for temp_codigo, roles_dict in ROLES_DESTACADOS.items():
        if temp_codigo not in temporadas_map or not roles_dict:
            continue

        temporada_obj = temporadas_map[temp_codigo]
        stats_sin_roles = EstadisticasPartidoJugador.objects.filter(
            partido__jornada__temporada=temporada_obj,
            roles=[],
        ).select_related("jugador")[:50000]

        for stat in stats_sin_roles:
            try:
                jugador_nombre = f"{stat.jugador.nombre} {stat.jugador.apellido}".strip()
                nombre_norm = normalizar_texto(jugador_nombre)

                if nombre_norm in roles_dict:
                    stat.roles = roles_dict[nombre_norm]
                    stat.save(update_fields=["roles"])
                    contador_total += 1
            except Exception:
                pass

    con_roles = EstadisticasPartidoJugador.objects.exclude(roles=[]).count()
    _log.info("[FASE 2] Roles: %d actualizados, %d total con roles", contador_total, con_roles)


def fase_2b_cargar_goles():
    """FASE 2b: Carga goles en partidos - DESHABILITADO (datos inflados en CSVs)."""
    logging.getLogger(__name__).info("[FASE 2b] Carga de goles deshabilitada.")


def fase_2c_cargar_clasificacion():
    """FASE 2c: Carga clasificación jornada."""
    _log = logging.getLogger(__name__)

    temporadas_map = {
        "temporada_23_24": "23_24",
        "temporada_24_25": "24_25",
        "temporada_25_26": "25_26",
    }

    data_dir = os.path.join(settings.BASE_DIR, "data")
    creadas = 0

    for temp_dir, temp_codigo in temporadas_map.items():
        csv_path = os.path.join(data_dir, temp_dir, "clasificacion_temporada.csv")
        if not os.path.exists(csv_path):
            continue

        try:
            df = pd.read_csv(csv_path, encoding="utf-8-sig")
            temporada = Temporada.objects.get(nombre=temp_codigo)

            for _, row in df.iterrows():
                try:
                    jornada_num = int(row["jornada"])
                    equipo_nombre = normalizar_equipo_bd(row["equipo"])

                    jornada = Jornada.objects.get(temporada=temporada, numero_jornada=jornada_num)
                    equipo = Equipo.objects.get(nombre=equipo_nombre)

                    _, created = ClasificacionJornada.objects.update_or_create(
                        temporada=temporada,
                        jornada=jornada,
                        equipo=equipo,
                        defaults={
                            "posicion": int(row["posicion"]),
                            "puntos": int(row["pts"]),
                            "goles_favor": int(row["gf"]),
                            "goles_contra": int(row["gc"]),
                            "diferencia_goles": int(row["dg"]),
                            "partidos_ganados": int(row["pg"]),
                            "partidos_empatados": int(row["pe"]),
                            "partidos_perdidos": int(row["pp"]),
                            "racha_reciente": str(row.get("racha5partidos", "")),
                        },
                    )

                    if created:
                        creadas += 1
                except Exception:
                    continue
        except Exception:
            continue

    _log.info(
        "[FASE 2c] Clasificación: %d nuevos, %d total",
        creadas,
        ClasificacionJornada.objects.count(),
    )


def fase_2d_cargar_rendimiento():
    """FASE 2d: Carga rendimiento histórico."""
    _log = logging.getLogger(__name__)

    creados = 0
    eqt_list = EquipoJugadorTemporada.objects.all().select_related("jugador", "equipo", "temporada")

    for eqt in eqt_list:
        try:
            temporada = eqt.temporada
            equipo = eqt.equipo
            jugador = eqt.jugador

            stats = EstadisticasPartidoJugador.objects.filter(
                jugador=jugador,
                partido__jornada__temporada=temporada,
                partido__equipo_local=equipo,
            ) | EstadisticasPartidoJugador.objects.filter(
                jugador=jugador,
                partido__jornada__temporada=temporada,
                partido__equipo_visitante=equipo,
            )

            if not stats.exists():
                continue

            _, created = RendimientoHistoricoJugador.objects.update_or_create(
                jugador=jugador,
                temporada=temporada,
                equipo=equipo,
                defaults={
                    "partidos_jugados": stats.filter(min_partido__gt=0).count(),
                    "partidos_como_titular": stats.filter(titular=True).count(),
                    "minutos_totales": int(stats.aggregate(Sum("min_partido"))["min_partido__sum"] or 0),
                    "goles_temporada": int(stats.aggregate(Sum("gol_partido"))["gol_partido__sum"] or 0),
                    "asistencias_temporada": int(stats.aggregate(Sum("asist_partido"))["asist_partido__sum"] or 0),
                    "tarjetas_amarillas_total": int(stats.aggregate(Sum("amarillas"))["amarillas__sum"] or 0),
                    "tarjetas_rojas_total": int(stats.aggregate(Sum("rojas"))["rojas__sum"] or 0),
                    "pases_completados_total": int(stats.aggregate(Sum("pases_totales"))["pases_totales__sum"] or 0),
                },
            )

            if created:
                creados += 1
        except Exception:
            continue

    _log.info(
        "[FASE 2d] Rendimiento: %d nuevos, %d total",
        creados,
        RendimientoHistoricoJugador.objects.count(),
    )


def fase_2e_poblar_equipo_jugador_temporada():
    """FASE 2e: Puebla EquipoJugadorTemporada con edad/partidos por temporada."""
    _log = logging.getLogger(__name__)

    total_actualizado = 0

    for temporada in Temporada.objects.all():
        eqt_list = EquipoJugadorTemporada.objects.filter(temporada=temporada)

        for eqt in eqt_list:
            jugador_id = eqt.jugador_id

            edad_max = (
                EstadisticasPartidoJugador.objects.filter(
                    jugador_id=jugador_id,
                    partido__jornada__temporada=temporada,
                    edad__isnull=False,
                ).aggregate(max_edad=Max("edad"))["max_edad"]
            )

            partidos_count = EstadisticasPartidoJugador.objects.filter(
                jugador_id=jugador_id,
                partido__jornada__temporada=temporada,
                min_partido__gt=0,
            ).count()

            if (edad_max and eqt.edad != edad_max) or eqt.partidos_jugados != partidos_count:
                eqt.edad = edad_max
                eqt.partidos_jugados = partidos_count
                eqt.save(update_fields=["edad", "partidos_jugados"])
                total_actualizado += 1

    _log.info(
        "[FASE 2e] EquipoJugadorTemporada: %d total, %d actualizados",
        EquipoJugadorTemporada.objects.count(),
        total_actualizado,
    )
    return total_actualizado


def fase_2f_completar_estadios():
    """FASE 2f: Completa estadios faltantes como fallback."""
    _log = logging.getLogger(__name__)

    estadios_fallback = {
        "Real Valladolid": "José Zorrilla",
        "Granada": "Nuevo Estadio de Los Cármenes",
        "Cádiz": "Estadio Ramón Blance",
        "UD Las Palmas": "Estadio de Gran Canaria",
        "Levante": "Estadio Ciutat de Valencia",
        "Almería": "Estadio Power Horse Stadium",
        "Real Oviedo": "Estadio Carlos Tartiere",
        "Girona": "Estadi Municipal de Montilivi",
        "Getafe": "Coliseum Alfonso Pérez",
        "Rayo Vallecano": "Estadio de Vallecas",
        "Barcelona": "Spotify Camp Nou",
        "Real Madrid": "Santiago Bernabéu",
        "Atlético Madrid": "Riyadh Air Metropolitano",
        "Valencia": "Estadio de Mestalla",
        "Real Sociedad": "Reale Arena",
        "Athletic Club": "San Mamés",
        "Villarreal": "La Cerámica",
        "Real Betis": "Benito Villamarín",
        "Sevilla": "Ramón Sánchez-Pizjuán",
        "Osasuna": "El Sadar",
        "Celta Vigo": "Balaídos",
        "RCD Mallorca": "Estadi de Son Moix",
        "Elche": "Estadio Martínez Valero",
        "RCD Espanyol": "Estadio Cornellà-El Prat",
        "Alavés": "Estadio de Mendizorrotza",
        "CA Osasuna": "El Sadar",
    }

    actualizados = 0
    for equipo in Equipo.objects.all():
        if not equipo.estadio or equipo.estadio.strip() == "":
            estadio = estadios_fallback.get(equipo.nombre)
            if estadio:
                equipo.estadio = estadio
                equipo.save(update_fields=["estadio"])
                actualizados += 1

    _log.info("[FASE 2f] Estadios completados: %d", actualizados)
