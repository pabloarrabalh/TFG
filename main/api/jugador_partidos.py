from collections import defaultdict

from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from .common import get_latest_temporada, jugador_payload_basic, parse_unique_positive_int_ids
from ..models import EquipoJugadorTemporada, EstadisticasPartidoJugador, Jugador


def _partidos_info(stats, jugador_equipo_id):
    partidos = []
    for stat in stats[:5]:
        p = stat.partido
        if jugador_equipo_id and p.equipo_local_id == jugador_equipo_id:
            rival_nombre = p.equipo_visitante.nombre
        elif jugador_equipo_id and p.equipo_visitante_id == jugador_equipo_id:
            rival_nombre = p.equipo_local.nombre
        else:
            rival_nombre = "TBD"

        fecha_str = p.fecha_partido.strftime("%d/%m") if p.fecha_partido else None
        partidos.append(
            {
                "jornada": p.jornada.numero_jornada,
                "rival": rival_nombre,
                "minutos": stat.min_partido or 0,
                "puntos": stat.puntos_fantasy if stat.puntos_fantasy and stat.puntos_fantasy > 0 else None,
                "fecha": fecha_str,
            }
        )
    return partidos


class JugadorPartidosView(APIView):
    """GET /api/jugador-partidos/?jugador_id=123&jornada_actual=12"""

    permission_classes = [AllowAny]

    def get(self, request):
        jugador_id = request.GET.get("jugador_id")
        jornada_actual = request.GET.get("jornada_actual")

        if not jugador_id or not jornada_actual:
            return Response({"error": "Parámetros requeridos", "partidos": []}, status=200)

        try:
            jugador = Jugador.objects.get(id=jugador_id)
        except (Jugador.DoesNotExist, ValueError, TypeError):
            return Response({"jugador": {"id": jugador_id}, "partidos": []}, status=200)

        temporada = get_latest_temporada()
        if not temporada:
            return Response({"jugador": {"id": jugador_id}, "partidos": []}, status=200)

        try:
            ultimos_partidos = list(
                EstadisticasPartidoJugador.objects.filter( jugador=jugador,partido__jornada__temporada=temporada,)
                .select_related("partido", "partido__equipo_local", "partido__equipo_visitante", "partido__jornada")
                .order_by("-partido__jornada__numero_jornada")[:5]
            )

            ejt = (EquipoJugadorTemporada.objects.filter(jugador=jugador, temporada=temporada).select_related("equipo").first())
            jugador_equipo_id = ejt.equipo_id if ejt else None

            return Response(
                {
                    "jugador": jugador_payload_basic(jugador.id, jugador),
                    "partidos": _partidos_info(ultimos_partidos, jugador_equipo_id),
                },
                status=200,
            )
        except Exception:
            return Response({"jugador": {"id": jugador_id}, "partidos": []}, status=200)


class JugadorPartidosBatchView(APIView):
    """POST /api/jugador-partidos-batch/."""
    permission_classes = [AllowAny]

    def post(self, request):
        jornada_actual = request.data.get("jornada_actual")
        if jornada_actual is None:
            return Response({"error": "Parámetros requeridos", "partidos_por_jugador": {}}, status=200)

        try:
            int(jornada_actual) 
        except (ValueError, TypeError):
            return Response({"error": "Parámetros requeridos", "partidos_por_jugador": {}}, status=200)

        jugador_ids = parse_unique_positive_int_ids(request.data.get("jugador_ids"))
        if not jugador_ids:
            return Response({"partidos_por_jugador": {}}, status=200)

        temporada = get_latest_temporada()
        if not temporada:
            return Response({"partidos_por_jugador": {}}, status=200)

        try:
            jugadores = {j.id: j for j in Jugador.objects.filter(id__in=jugador_ids)}
            eq_map = {
                row["jugador_id"]: row["equipo_id"]
                for row in EquipoJugadorTemporada.objects.filter(
                    jugador_id__in=jugador_ids,
                    temporada=temporada,
                ).values("jugador_id", "equipo_id")
            }

            stats = (
                EstadisticasPartidoJugador.objects.filter(jugador_id__in=jugador_ids, partido__jornada__temporada=temporada,)
                .select_related("partido", "partido__equipo_local", "partido__equipo_visitante", "partido__jornada")
                .order_by("jugador_id", "-partido__jornada__numero_jornada")
            )

            grouped_stats = defaultdict(list)
            for stat in stats:
                if len(grouped_stats[stat.jugador_id]) >= 5:
                    continue
                grouped_stats[stat.jugador_id].append(stat)

            partidos_por_jugador = {}
            for jid in jugador_ids:
                partidos_por_jugador[str(jid)] = _partidos_info(grouped_stats.get(jid, []), eq_map.get(jid))

            return Response(
                {
                    "partidos_por_jugador": partidos_por_jugador,
                    "jugadores": {
                        str(jid): jugador_payload_basic(jid, jugadores.get(jid))
                        for jid in jugador_ids
                    },
                },
                status=200,
            )
        except Exception:
            return Response(
                {
                    "error": "Error procesando lote de jugadores",
                    "partidos_por_jugador": {str(jid): [] for jid in jugador_ids},
                },
                status=200,
            )
