import logging

from django.db.models import Count, Sum
from scipy import stats as scipy_stats

from main.models import EquipoJugadorTemporada, EstadisticasPartidoJugador


def fase_4_precalcular_percentiles():
    """Precalcula y almacena percentiles para todos los EquipoJugadorTemporada."""
    _log = logging.getLogger(__name__)

    stat_fields = [
        "gol_partido",
        "asist_partido",
        "tiro_puerta_partido",
        "tiros",
        "xg_partido",
        "despejes",
        "entradas",
        "bloqueos",
        "pases_totales",
        "pases_clave",
        "faltas_cometidas",
        "regates",
        "regates_completados",
        "conducciones",
        "duelos",
        "amarillas",
        "goles_en_contra",
        "porcentaje_paradas",
        "psxg",
    ]

    stats_grupos = {
        "ataque": {
            "goles": "gol_partido",
            "asistencias": "asist_partido",
            "tiros_puerta": "tiro_puerta_partido",
            "tiros": "tiros",
            "xg": "xg_partido",
        },
        "defensa": {
            "despejes": "despejes",
            "entradas": "entradas",
            "bloqueos": "bloqueos",
        },
        "organizacion": {
            "pases_totales": "pases_totales",
            "pases_clave": "pases_clave",
            "faltas_cometidas": "faltas_cometidas",
        },
        "regates_block": {
            "regates": "regates",
            "regates_completados": "regates_completados",
            "conducciones": "conducciones",
            "duelos": "duelos",
        },
        "comportamiento": {
            "amarillas": "amarillas",
        },
        "portero": {
            "goles_en_contra": "goles_en_contra",
            "porcentaje_paradas": "porcentaje_paradas",
            "psxg": "psxg",
        },
    }

    all_records = list(EquipoJugadorTemporada.objects.select_related("jugador", "temporada"))
    total_records = len(all_records)
    _log.info("[FASE 4] Precalculando percentiles para %d registros...", total_records)

    stats_cache = {}
    temporada_ids = set(r.temporada_id for r in all_records)

    for temporada_id in temporada_ids:
        stats_cache[temporada_id] = {}
        all_stats_temp = EstadisticasPartidoJugador.objects.filter(
            partido__jornada__temporada_id=temporada_id
        ).values("jugador_id").annotate(**{f: Sum(f) for f in stat_fields})
        for row in all_stats_temp:
            stats_cache[temporada_id][row["jugador_id"]] = {f: row.get(f, 0) for f in stat_fields}

    position_cache = {}
    for temporada_id in temporada_ids:
        position_cache[temporada_id] = {}
        pos_data = (
            EstadisticasPartidoJugador.objects.filter(
                partido__jornada__temporada_id=temporada_id,
                posicion__isnull=False,
            )
            .values("jugador_id", "posicion")
            .annotate(cnt=Count("id"))
            .order_by("jugador_id", "-cnt")
        )

        seen = set()
        for row in pos_data:
            jugador_id = row["jugador_id"]
            if jugador_id not in seen and row["posicion"]:
                seen.add(jugador_id)
                position_cache[temporada_id][jugador_id] = row["posicion"]

    to_update = []

    for ejt in all_records:
        posicion = position_cache.get(ejt.temporada_id, {}).get(ejt.jugador_id)
        if not posicion:
            continue

        ejt.posicion = posicion
        stats_jugador = stats_cache.get(ejt.temporada_id, {}).get(
            ejt.jugador_id,
            {k: 0 for k in stat_fields},
        )

        peers_stats_dict = {}
        for jug_id, stats in stats_cache.get(ejt.temporada_id, {}).items():
            if position_cache.get(ejt.temporada_id, {}).get(jug_id) == posicion:
                peers_stats_dict[jug_id] = stats

        if not peers_stats_dict:
            to_update.append(ejt)
            continue

        percentiles = {}
        for grupo, alias_map in stats_grupos.items():
            percentiles[grupo] = {}
            for alias, campo_real in alias_map.items():
                valor_jugador = stats_jugador.get(campo_real, 0) or 0
                valores_peers = [s.get(campo_real, 0) or 0 for s in peers_stats_dict.values()]

                if valores_peers:
                    try:
                        percentil = scipy_stats.percentileofscore(
                            valores_peers,
                            valor_jugador,
                            nan_policy="omit",
                        )
                        percentiles[grupo][alias] = round(float(percentil), 2)
                    except Exception:
                        percentiles[grupo][alias] = 0.0
                else:
                    percentiles[grupo][alias] = 0.0

        ejt.percentiles = percentiles
        to_update.append(ejt)

    if to_update:
        EquipoJugadorTemporada.objects.bulk_update(
            to_update,
            ["posicion", "percentiles"],
            batch_size=500,
        )

    _log.info("[FASE 4] Percentiles actualizados: %d registros", len(to_update))
