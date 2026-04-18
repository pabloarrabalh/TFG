import importlib
import math
import sys as _sys
import threading as _th
from pathlib import Path

from django.core.cache import cache
from django.db.models import Count

from ..models import Calendario, EquipoJugadorTemporada, EstadisticasPartidoJugador, Jornada, Partido, PrediccionJugador, Temporada
from ..views.utils import shield_name

# Background computation state (prevent duplicate simultaneous runs)
_BG_LOCK = _th.Lock()
_BG_RUNNING: set = set()  # set of (temporada_id, jornada_num)


def serialize_partido_calendario(calendario):
    return {
        "id": calendario.id,
        "equipo_local": calendario.equipo_local.nombre,
        "equipo_visitante": calendario.equipo_visitante.nombre,
        "equipo_local_escudo": shield_name(calendario.equipo_local.nombre),
        "equipo_visitante_escudo": shield_name(calendario.equipo_visitante.nombre),
        "fecha": calendario.fecha.strftime("%Y-%m-%d") if calendario.fecha else None,
        "hora": str(calendario.hora) if calendario.hora else None,
        "jornada": calendario.jornada.numero_jornada if calendario.jornada else None,
    }


def get_jugadores_destacados_con_predicciones(temporada, proxima_jornada):
    resultado = {}
    if not proxima_jornada or not temporada:
        return resultado

    posiciones = ["Portero", "Defensa", "Centrocampista", "Delantero"]

    ejt_map = {
        e["jugador_id"]: e
        for e in EquipoJugadorTemporada.objects.filter(temporada=temporada).values(
            "jugador_id",
            "jugador__nombre",
            "jugador__apellido",
            "equipo_id",
            "equipo__nombre",
            "posicion",
            "dorsal",
        )
    }

    _played_nums = list(
        Partido.objects.filter(jornada__temporada=temporada, goles_local__isnull=False)
        .values_list("jornada__numero_jornada", flat=True)
        .distinct()
        .order_by("-jornada__numero_jornada")[:3]
    )
    if len(_played_nums) < 3:
        skip_pocos_minutos = set()
    else:
        _min_sum_fast: dict = {}
        for _row in (
            EstadisticasPartidoJugador.objects.filter(
                partido__jornada__temporada=temporada,
                partido__jornada__numero_jornada__in=_played_nums,
            ).values("jugador_id", "min_partido")
        ):
            _jid = _row["jugador_id"]
            _min_sum_fast[_jid] = _min_sum_fast.get(_jid, 0) + (_row["min_partido"] or 0)
        skip_pocos_minutos = {jid for jid in ejt_map if _min_sum_fast.get(jid, 0) < 60}

    pred_rows = (
        PrediccionJugador.objects.filter(jornada=proxima_jornada)
        .values("jugador_id", "jugador__nombre", "jugador__apellido", "prediccion", "modelo")
        .order_by("-creada_en")
    )

    pred_map = {}
    for row in pred_rows:
        jid = row["jugador_id"]
        if jid not in pred_map:
            try:
                val = float(row["prediccion"])
                if not math.isfinite(val):
                    continue
                if val != val:
                    continue
            except (TypeError, ValueError):
                continue
            pred_map[jid] = row

    rival_map = {}
    for cal in Calendario.objects.filter(jornada=proxima_jornada).values(
        "equipo_local_id",
        "equipo_visitante_id",
        "equipo_local__nombre",
        "equipo_visitante__nombre",
    ):
        rival_map[cal["equipo_local_id"]] = cal["equipo_visitante__nombre"]
        rival_map[cal["equipo_visitante_id"]] = cal["equipo_local__nombre"]

    candidatos_pos = {pos: [] for pos in posiciones}
    for jugador_id, pred in pred_map.items():
        ejt = ejt_map.get(jugador_id)
        if not ejt:
            continue
        if jugador_id in skip_pocos_minutos:
            continue
        posicion = ejt["posicion"] or "Delantero"
        if posicion not in posiciones:
            continue
        candidatos_pos[posicion].append(
            {
                "id": jugador_id,
                "nombre": pred["jugador__nombre"],
                "apellido": pred["jugador__apellido"],
                "posicion": posicion,
                "equipo": ejt["equipo__nombre"],
                "equipo_escudo": shield_name(ejt["equipo__nombre"]),
                "dorsal": str(ejt["dorsal"]) if ejt["dorsal"] else "-",
                "prediccion": round(float(pred["prediccion"]), 2),
                "proximo_rival": rival_map.get(ejt["equipo_id"], "-"),
            }
        )

    for posicion in posiciones:
        candidatos_pos[posicion].sort(key=lambda x: x["prediccion"], reverse=True)
        resultado[posicion] = candidatos_pos[posicion][:3]

    return resultado


def _bg_compute_predictions(temporada_id, jornada_num, cache_key):
    try:
        temporada = Temporada.objects.get(pk=temporada_id)
        jornada_obj = Jornada.objects.get(temporada=temporada, numero_jornada=jornada_num)
    except Exception:
        return

    entren_path = Path(__file__).resolve().parents[2] / "entrenamientoModelos"
    if str(entren_path) not in _sys.path:
        _sys.path.insert(0, str(entren_path))
    try:
        mod = importlib.import_module("predecir")
        predecir_puntos = getattr(mod, "predecir_puntos")
    except Exception:
        return

    _POS_CODE = {"Portero": "PT", "Defensa": "DF", "Centrocampista": "MC", "Delantero": "DT"}
    _POS_MODEL = {"PT": "rf", "DF": "rf", "MC": "ridge", "DT": "ridge"}
    posiciones_validas = set(_POS_CODE.keys())

    pos_fallback = {}
    for row in (
        EstadisticasPartidoJugador.objects.filter(
            partido__jornada__temporada=temporada,
            posicion__isnull=False,
        )
        .exclude(posicion="")
        .values("jugador_id", "posicion")
        .annotate(cnt=Count("id"))
        .order_by("jugador_id", "-cnt")
    ):
        if row["jugador_id"] not in pos_fallback:
            pos_fallback[row["jugador_id"]] = row["posicion"]

    ejt_list = list(
        EquipoJugadorTemporada.objects.filter(temporada=temporada).values(
            "jugador_id",
            "jugador__nombre",
            "jugador__apellido",
            "equipo_id",
            "equipo__nombre",
            "posicion",
            "dorsal",
        )
    )

    _played_nums_bg = list(
        Partido.objects.filter(jornada__temporada=temporada, goles_local__isnull=False)
        .values_list("jornada__numero_jornada", flat=True)
        .distinct()
        .order_by("-jornada__numero_jornada")[:3]
    )
    if len(_played_nums_bg) < 3:
        skip_pocos_minutos_bg = set()
    else:
        _min_sum_bg: dict = {}
        for _row in (
            EstadisticasPartidoJugador.objects.filter(
                partido__jornada__temporada=temporada,
                partido__jornada__numero_jornada__in=_played_nums_bg,
            ).values("jugador_id", "min_partido")
        ):
            _jid = _row["jugador_id"]
            _min_sum_bg[_jid] = _min_sum_bg.get(_jid, 0) + (_row["min_partido"] or 0)
        all_player_ids_bg = set(ejt["jugador_id"] for ejt in ejt_list)
        skip_pocos_minutos_bg = {jid for jid in all_player_ids_bg if _min_sum_bg.get(jid, 0) < 60}

    rival_map = {}
    for cal in Calendario.objects.filter(jornada=jornada_obj).values(
        "equipo_local_id",
        "equipo_visitante_id",
        "equipo_local__nombre",
        "equipo_visitante__nombre",
    ):
        rival_map[cal["equipo_local_id"]] = cal["equipo_visitante__nombre"]
        rival_map[cal["equipo_visitante_id"]] = cal["equipo_local__nombre"]

    candidatos = {pos: [] for pos in posiciones_validas}
    seen = set()

    for ejt in ejt_list:
        jid = ejt["jugador_id"]
        if jid in seen:
            continue
        seen.add(jid)
        if jid in skip_pocos_minutos_bg:
            continue
        posicion = ejt.get("posicion") or pos_fallback.get(jid)
        if posicion not in posiciones_validas:
            continue
        pos_code = _POS_CODE[posicion]
        try:
            result = predecir_puntos(jid, pos_code, jornada_num, verbose=False)
            if not isinstance(result, dict) or result.get("error"):
                continue
            pts = result.get("prediccion") or result.get("puntos_predichos")
            if pts is None:
                continue
            try:
                pts_f = float(pts)
                if not math.isfinite(pts_f):
                    continue
            except (TypeError, ValueError):
                continue
            PrediccionJugador.objects.update_or_create(
                jugador_id=jid,
                jornada=jornada_obj,
                modelo=_POS_MODEL.get(pos_code, "rf"),
                defaults={"prediccion": float(pts_f)},
            )
            candidatos[posicion].append(
                {
                    "id": jid,
                    "nombre": ejt["jugador__nombre"],
                    "apellido": ejt["jugador__apellido"],
                    "posicion": posicion,
                    "equipo": ejt["equipo__nombre"],
                    "equipo_escudo": shield_name(ejt["equipo__nombre"]),
                    "dorsal": str(ejt["dorsal"]) if ejt["dorsal"] else "-",
                    "prediccion": round(float(pts_f), 2),
                    "proximo_rival": rival_map.get(ejt["equipo_id"], "-"),
                }
            )
        except Exception:
            continue

    resultado = {}
    for pos in posiciones_validas:
        candidatos[pos].sort(key=lambda x: x["prediccion"], reverse=True)
        resultado[pos] = candidatos[pos][:3]

    if any(len(v) > 0 for v in resultado.values()):
        cache.set(cache_key, resultado, 1800)


def schedule_bg_predictions(temporada, jornada_num, cache_key):
    key = (temporada.id, jornada_num)
    with _BG_LOCK:
        if key in _BG_RUNNING:
            return
        _BG_RUNNING.add(key)

    def _run():
        try:
            _bg_compute_predictions(temporada.id, jornada_num, cache_key)
        finally:
            with _BG_LOCK:
                _BG_RUNNING.discard(key)

    _th.Thread(target=_run, daemon=True, name=f"PredBG-j{jornada_num}").start()
