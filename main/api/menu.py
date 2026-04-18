from django.core.cache import cache
from django.db.models import Q
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from .common import get_latest_temporada, parse_int
from ..models import Calendario, ClasificacionJornada, Jornada, Partido
from ..views.utils import shield_name
from ..utils.menu_service import (
    get_jugadores_destacados_con_predicciones,
    schedule_bg_predictions,
    serialize_partido_calendario,
)


class MenuView(APIView):
    """GET /api/menu/?jornada=6"""

    permission_classes = [AllowAny]

    def get(self, request):
        temporada = get_latest_temporada()
        empty = {
            "clasificacion_top": [],
            "partidos_proxima_jornada": [],
            "partidos_favoritos": [],
            "jornada_actual": None,
            "proxima_jornada": None,
            "jugadores_destacados_por_posicion": {},
        }
        if not temporada:
            return Response(empty)

        jornada_param = request.query_params.get("jornada")
        jornada_actual = None

        jornada_num = parse_int(jornada_param, default=None, min_value=1) if jornada_param else None
        if jornada_num is not None:
            jornada_actual = Jornada.objects.filter(
                temporada=temporada,
                numero_jornada=jornada_num,
            ).first()
        else:
            last_played_num = (
                Partido.objects.filter(
                    jornada__temporada=temporada,
                    goles_local__isnull=False,
                )
                .order_by("-jornada__numero_jornada")
                .values_list("jornada__numero_jornada", flat=True)
                .first()
            )
            if last_played_num:
                jornada_actual = Jornada.objects.filter(
                    temporada=temporada,
                    numero_jornada=last_played_num,
                ).first()
            else:
                jornada_actual = (
                    Jornada.objects.filter(temporada=temporada)
                    .order_by("numero_jornada")
                    .first()
                )

        clasificacion_top = []
        if jornada_actual:
            qs = (
                ClasificacionJornada.objects.filter(temporada=temporada, jornada=jornada_actual)
                .order_by("posicion")[:5]
                .select_related("equipo")
            )
            for reg in qs:
                clasificacion_top.append(
                    {
                        "posicion": reg.posicion,
                        "equipo": reg.equipo.nombre,
                        "equipo_escudo": shield_name(reg.equipo.nombre),
                        "puntos": reg.puntos,
                    }
                )

        proxima_jornada = None
        partidos_proxima = []
        if jornada_actual:
            proxima_jornada = Jornada.objects.filter(
                temporada=temporada,
                numero_jornada=jornada_actual.numero_jornada + 1,
            ).first()
            if proxima_jornada:
                for partido in (
                    Calendario.objects.filter(jornada=proxima_jornada)
                    .select_related("equipo_local", "equipo_visitante")
                    .order_by("fecha", "hora")
                ):
                    partidos_proxima.append(serialize_partido_calendario(partido))

        partidos_favoritos = []
        if request.user.is_authenticated and proxima_jornada:
            fav_ids = set(request.user.equipos_favoritos.values_list("equipo_id", flat=True))
            if fav_ids:
                for partido in (
                    Calendario.objects.filter(jornada=proxima_jornada)
                    .filter(Q(equipo_local_id__in=fav_ids) | Q(equipo_visitante_id__in=fav_ids))
                    .select_related("equipo_local", "equipo_visitante")
                ):
                    partidos_favoritos.append(serialize_partido_calendario(partido))

        jugadores_destacados = get_jugadores_destacados_con_predicciones(temporada, proxima_jornada)

        return Response(
            {
                "clasificacion_top": clasificacion_top,
                "jornada_actual": {"numero": jornada_actual.numero_jornada} if jornada_actual else None,
                "proxima_jornada": {"numero": proxima_jornada.numero_jornada} if proxima_jornada else None,
                "partidos_proxima_jornada": partidos_proxima,
                "partidos_favoritos": partidos_favoritos,
                "jugadores_destacados_por_posicion": jugadores_destacados,
            }
        )


class MenuTopJugadoresView(APIView):
    """GET /api/menu/top-jugadores/?jornada=18"""

    permission_classes = [AllowAny]

    def get(self, request):
        jornada_param = request.query_params.get("jornada")
        if not jornada_param:
            return Response({"jugadores_destacados_por_posicion": {}})

        cache_key = f"menu_top_jug:{jornada_param}"
        cached = cache.get(cache_key)
        if cached is not None:
            return Response({"jugadores_destacados_por_posicion": cached})

        jornada_num = parse_int(jornada_param, default=None, min_value=1)
        if jornada_num is None:
            return Response({"error": "jornada invalida"}, status=400)

        temporada = get_latest_temporada()
        if not temporada:
            return Response({"jugadores_destacados_por_posicion": {}})

        jornada_obj = Jornada.objects.filter(temporada=temporada, numero_jornada=jornada_num).first()
        if not jornada_obj:
            return Response({"jugadores_destacados_por_posicion": {}})

        resultado = get_jugadores_destacados_con_predicciones(temporada, jornada_obj)
        schedule_bg_predictions(temporada, jornada_num, cache_key)

        if any(len(v) > 0 for v in resultado.values()):
            cache.set(cache_key, resultado, 1800)

        return Response({"jugadores_destacados_por_posicion": resultado})
