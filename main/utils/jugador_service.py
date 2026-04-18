import sys
from pathlib import Path

from django.db.models import Avg, Count, Q, Sum

from predecir import predecir_puntos

from ..models import EquipoJugadorTemporada, EstadisticasPartidoJugador, Jornada, PrediccionJugador, Temporada


def _safe_float(value, default=0.0):
    if value is None:
        return float(default)
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def get_datos_temporada_completa(jugador, temporada):
    todas_jornadas = Jornada.objects.filter(temporada=temporada).order_by("numero_jornada")
    if not todas_jornadas.exists():
        return []

    pred_qs = PrediccionJugador.objects.filter(jugador=jugador, jornada__temporada=temporada)
    pred_by_jornada = {p.jornada_id: p for p in pred_qs}

    stats_qs = EstadisticasPartidoJugador.objects.filter(
        jugador=jugador,
        partido__jornada__temporada=temporada,
    ).select_related("partido__jornada")
    stats_by_jornada = {}
    for stat in stats_qs:
        jornada = stat.partido.jornada
        if jornada.pk not in stats_by_jornada:
            stats_by_jornada[jornada.pk] = []
        stats_by_jornada[jornada.pk].append(stat)

    result = []
    for jornada in todas_jornadas:
        pred = pred_by_jornada.get(jornada.pk)
        stats = stats_by_jornada.get(jornada.pk, [])

        real_pts = sum(s.puntos_fantasy or 0 for s in stats) if stats else None
        pred_value = round(pred.prediccion, 2) if pred and pred.prediccion is not None else None

        result.append(
            {
                "jornada": jornada.numero_jornada,
                "temporada": jornada.temporada.nombre.replace("_", "/"),
                "prediccion": pred_value,
                "real": real_pts,
                "modelo": pred.modelo if pred else None,
                "is_early_jornada": jornada.numero_jornada <= 5,
            }
        )

    return result


def get_ultimos_8_temporada_completa(jugador, temporada):
    todas_jornadas = Jornada.objects.filter(temporada=temporada).order_by("numero_jornada")
    if not todas_jornadas.exists():
        return []

    stats_qs = (
        EstadisticasPartidoJugador.objects.filter(jugador=jugador, partido__jornada__temporada=temporada)
        .exclude(puntos_fantasy__gt=40)
        .select_related("partido__jornada")
    )

    stats_by_jornada = {}
    for stat in stats_qs:
        jornada = stat.partido.jornada
        if jornada.pk not in stats_by_jornada:
            stats_by_jornada[jornada.pk] = stat

    result = []
    for jornada in todas_jornadas:
        stat = stats_by_jornada.get(jornada.pk)
        if stat:
            result.append(
                {
                    "puntos_fantasy": float(stat.puntos_fantasy or 0),
                    "partido": {"jornada": {"numero_jornada": stat.partido.jornada.numero_jornada}},
                }
            )
        else:
            result.append(
                {
                    "puntos_fantasy": None,
                    "partido": {"jornada": {"numero_jornada": jornada.numero_jornada}},
                }
            )

    return result


def get_predicciones_jugador(jugador, temporada):
    pred_qs = PrediccionJugador.objects.filter(jugador=jugador)
    if temporada:
        pred_qs = pred_qs.filter(jornada__temporada=temporada)
    predictions = list(pred_qs.select_related("jornada__temporada"))

    pred_by_jornada_id = {p.jornada_id: p for p in predictions}
    jornada_by_id = {p.jornada_id: p.jornada for p in predictions}

    stats_qs = EstadisticasPartidoJugador.objects.filter(jugador=jugador)
    if temporada:
        stats_qs = stats_qs.filter(partido__jornada__temporada=temporada)

    real_by_jornada_id = {}
    for stat in stats_qs.select_related("partido__jornada__temporada"):
        jornada = stat.partido.jornada
        real_by_jornada_id[jornada.pk] = real_by_jornada_id.get(jornada.pk, 0) + (stat.puntos_fantasy or 0)
        jornada_by_id[jornada.pk] = jornada

    result = []
    for jornada_id, jornada in jornada_by_id.items():
        pred = pred_by_jornada_id.get(jornada_id)
        real = real_by_jornada_id.get(jornada_id)

        pred_value = round(_safe_float(pred.prediccion), 2) if pred and pred.prediccion is not None else None
        real_value = _safe_float(real) if real is not None else None

        result.append(
            {
                "jornada": jornada.numero_jornada,
                "temporada": jornada.temporada.nombre.replace("_", "/"),
                "prediccion": pred_value,
                "real": real_value,
                "modelo": pred.modelo if pred else None,
                "is_early_jornada": jornada.numero_jornada <= 5,
            }
        )

    result.sort(key=lambda x: x["jornada"])
    return result


def generar_predicciones_faltantes(jugador, temporada):
    if not jugador or not temporada:
        return

    try:
        entrenamientos_path = Path(__file__).resolve().parents[2] / "entrenamientoModelos"
        if str(entrenamientos_path) not in sys.path:
            sys.path.insert(0, str(entrenamientos_path))

        ejt = EquipoJugadorTemporada.objects.filter(jugador=jugador, temporada=temporada).first()
        posicion = ejt.posicion if ejt else (jugador.get_posicion_mas_frecuente() or "Delantero")
        jornadas = Jornada.objects.filter(temporada=temporada).order_by("numero_jornada")

        for jornada in jornadas:
            if PrediccionJugador.objects.filter(jugador=jugador, jornada=jornada).exists():
                continue

            try:
                modelo_para_pred = "Baseline" if jornada.numero_jornada <= 5 else None

                resultado = predecir_puntos(
                    jugador.pk,
                    posicion,
                    jornada_actual=jornada.numero_jornada,
                    verbose=False,
                    modelo_tipo=modelo_para_pred,
                )

                if resultado and isinstance(resultado, dict) and not resultado.get("error"):
                    prediction = resultado.get("prediccion")
                    if prediction is not None:
                        modelo_usado = "baseline" if jornada.numero_jornada <= 5 else "rf"
                        PrediccionJugador.objects.update_or_create(
                            jugador=jugador,
                            jornada=jornada,
                            modelo=modelo_usado,
                            defaults={"prediccion": float(prediction)},
                        )
            except Exception:
                continue
    except Exception:
        return


def build_roles(jugador, temporada, es_carrera):
    if es_carrera:
        roles_por_temporada = []
        for ejt in (
            EquipoJugadorTemporada.objects.filter(jugador=jugador)
            .select_related("temporada")
            .order_by("-temporada__nombre")[:3]
        ):
            stats_con_roles = (
                EstadisticasPartidoJugador.objects.filter(
                    jugador=jugador,
                    partido__jornada__temporada=ejt.temporada,
                    roles__isnull=False,
                )
                .exclude(puntos_fantasy__gt=40)
                .exclude(roles__exact=[])
                .values_list("roles", flat=True)
            )
            roles_dict = {}
            for stats_roles in stats_con_roles:
                if stats_roles and isinstance(stats_roles, list):
                    for role_obj in stats_roles:
                        if isinstance(role_obj, dict):
                            for fn, values in role_obj.items():
                                if fn not in roles_dict or values[0] < roles_dict[fn][0]:
                                    roles_dict[fn] = values
            if roles_dict:
                roles_por_temporada.append(
                    {
                        "temporada": ejt.temporada.nombre.replace("_", "/"),
                        "roles": [{k: v} for k, v in roles_dict.items()],
                    }
                )
        return roles_por_temporada

    stats_con_roles = (
        EstadisticasPartidoJugador.objects.filter(
            jugador=jugador,
            partido__jornada__temporada=temporada,
            roles__isnull=False,
        )
        .exclude(puntos_fantasy__gt=40)
        .exclude(roles__exact=[])
        .values_list("roles", flat=True)
    )
    roles_dict = {}
    for stats_roles in stats_con_roles:
        if stats_roles and isinstance(stats_roles, list):
            for role_obj in stats_roles:
                if isinstance(role_obj, dict):
                    for fn, values in role_obj.items():
                        if fn not in roles_dict or values[0] < roles_dict[fn][0]:
                            roles_dict[fn] = values
    return [{k: v} for k, v in roles_dict.items()] if roles_dict else []


def build_historico(jugador):
    historico_data = []
    for hist in (
        EquipoJugadorTemporada.objects.filter(jugador=jugador)
        .select_related("equipo", "temporada")
        .order_by("-temporada__nombre")
    ):
        sh = (
            EstadisticasPartidoJugador.objects.filter(
                jugador=jugador,
                partido__jornada__temporada=hist.temporada,
            )
            .exclude(puntos_fantasy__gt=40)
            .aggregate(
                goles=Sum("gol_partido"),
                asistencias=Sum("asist_partido"),
                minutos=Sum("min_partido"),
                partidos=Count("id", filter=Q(min_partido__gt=0)),
                puntos_totales=Sum("puntos_fantasy"),
                pases=Sum("pases_totales"),
                pases_accuracy=Avg("pases_completados_pct"),
                xag=Sum("xag"),
                despejes=Sum("despejes"),
                entradas=Sum("entradas"),
                duelos_ganados=Sum("duelos_ganados"),
                duelos_perdidos=Sum("duelos_perdidos"),
                amarillas=Sum("amarillas"),
                rojas=Sum("rojas"),
                bloqueos=Sum("bloqueos"),
                duelos_aereos_ganados=Sum("duelos_aereos_ganados"),
                duelos_aereos_perdidos=Sum("duelos_aereos_perdidos"),
                tiros=Sum("tiros"),
                tiros_puerta=Sum("tiro_puerta_partido"),
                xg=Sum("xg_partido"),
                regates_completados=Sum("regates_completados"),
                regates_fallidos=Sum("regates_fallidos"),
                conducciones=Sum("conducciones"),
                conducciones_progresivas=Sum("conducciones_progresivas"),
                distancia_conduccion=Sum("distancia_conduccion"),
            )
        )
        partidos = sh["partidos"] or 0
        puntos_totales = sh["puntos_totales"] or 0
        ppp = round(puntos_totales / partidos, 1) if partidos > 0 else 0
        historico_data.append(
            {
                "temporada": hist.temporada.nombre.replace("_", "/"),
                "equipo": hist.equipo.nombre,
                "dorsal": hist.dorsal or "-",
                "puntos_totales": puntos_totales,
                "puntos_por_partido": ppp,
                "goles": sh["goles"] or 0,
                "asistencias": sh["asistencias"] or 0,
                "pj": partidos,
                "minutos": sh["minutos"] or 0,
                "pases": sh["pases"] or 0,
                "pases_accuracy": round(_safe_float(sh["pases_accuracy"]), 1),
                "xag": round(_safe_float(sh["xag"]), 2),
                "despejes": sh["despejes"] or 0,
                "entradas": sh["entradas"] or 0,
                "duelos_totales": (sh["duelos_ganados"] or 0) + (sh["duelos_perdidos"] or 0),
                "amarillas": sh["amarillas"] or 0,
                "rojas": sh["rojas"] or 0,
                "bloqueos": sh["bloqueos"] or 0,
                "duelos_aereos_totales": (sh["duelos_aereos_ganados"] or 0) + (sh["duelos_aereos_perdidos"] or 0),
                "tiros": sh["tiros"] or 0,
                "tiros_puerta": sh["tiros_puerta"] or 0,
                "xg": round(_safe_float(sh["xg"]), 2),
                "regates_completados": sh["regates_completados"] or 0,
                "regates_fallidos": sh["regates_fallidos"] or 0,
                "conducciones": sh["conducciones"] or 0,
                "conducciones_progresivas": sh["conducciones_progresivas"] or 0,
                "distancia_conduccion": round(_safe_float(sh["distancia_conduccion"]), 1),
            }
        )
    return historico_data
