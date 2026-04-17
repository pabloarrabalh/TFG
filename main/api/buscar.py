"""
DRF API views – Search & Player Radar
Endpoints:
  GET  /api/radar/<jugador_id>/<temporada>/
  GET  /api/buscar/?q=QUERY
"""
import logging

from django.db.models import Count, Q, Sum
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from ..models import *
from ..meilisearch_docs import MEILISEARCH_AVAILABLE, meilisearch_client

logger = logging.getLogger(__name__)


# ── 1. RADAR CHART ────────────────────────────────────────────────────────────

class RadarJugadorView(APIView):
    """GET /api/radar/<jugador_id>/<temporada>/

    Returns normalised (0-100 percentile) radar-chart values for a player in
    a given season. Values are read from the pre-calculated EquipoJugadorTemporada.percentiles
    field (a single DB lookup) instead of being computed on every request.
    """
    permission_classes = [AllowAny]

    def get(self, request, jugador_id, temporada):
        try:
            jugador = Jugador.objects.get(id=jugador_id)
        except Jugador.DoesNotExist:
            return Response({'error': 'Jugador no encontrado'}, status=status.HTTP_404_NOT_FOUND)

        try:
            temp_obj = Temporada.objects.get(nombre=temporada)
        except Temporada.DoesNotExist:
            return Response({'error': 'Temporada no encontrada'}, status=status.HTTP_404_NOT_FOUND)

        # Single DB query: gives us posicion + percentiles already pre-calculated
        ejt = EquipoJugadorTemporada.objects.filter(
            jugador=jugador, temporada=temp_obj
        ).first()

        posicion = (ejt.posicion if ejt else None) or jugador.get_posicion_mas_frecuente()
        if not posicion:
            return Response({'radar_values': [50] * 7, 'media_general': 50})

        pct = (ejt.percentiles if ejt and ejt.percentiles else {})

        # One aggregate query for minutos/puntos (season-ongoing, not worth pre-storing)
        stats_jugador = (
            EstadisticasPartidoJugador.objects
            .filter(jugador=jugador, partido__jornada__temporada=temp_obj)
            .aggregate(
                total_minutos=Sum('min_partido'),
                total_puntos=Sum('puntos_fantasy'),
                partidos=Count('id', filter=Q(min_partido__gt=0)),
            )
        )
        minutos_totales = stats_jugador['total_minutos'] or 0
        minutos_percentil = min(100, (minutos_totales / 2700) * 100) if minutos_totales > 0 else 0
        puntos_totales = stats_jugador['total_puntos'] or 0
        partidos = stats_jugador['partidos'] or 1
        puntos_promedio = puntos_totales / partidos if partidos > 0 else 0
        puntos_percentil = min(100, (puntos_promedio / 10) * 100) if puntos_promedio > 0 else 0

        def _p(grupo, campo, default=50):
            """Read a pre-calculated percentile, falling back to default."""
            return pct.get(grupo, {}).get(campo, default)

        if posicion == 'Portero':
            radar_values = [
                round(_p('organizacion', 'pases_totales'), 1),
                round(minutos_percentil, 1),
                round(puntos_percentil, 1),
                round(100 - _p('comportamiento', 'amarillas'), 1),
                round(_p('portero', 'porcentaje_paradas'), 1),
                round(100 - _p('portero', 'goles_en_contra'), 1),
                round(_p('portero', 'psxg'), 1),
            ]
            labels = ['Pases', 'Minutos', 'Puntos', 'Comportamiento', 'Paradas %', 'GEC', 'PSxG']
        else:
            ataque_avg = (
                _p('ataque', 'goles') + _p('ataque', 'tiros_puerta') + _p('ataque', 'xg')
            ) / 3
            defensa_avg = (
                _p('defensa', 'despejes') + _p('defensa', 'entradas') + _p('regates_block', 'duelos')
            ) / 3
            regates_avg = (
                _p('regates_block', 'regates_completados') + _p('regates_block', 'conducciones')
            ) / 2
            pases_avg = (
                _p('organizacion', 'pases_totales') + _p('ataque', 'asistencias')
            ) / 2
            comportamiento_avg = 100 - _p('comportamiento', 'amarillas')

            radar_values = [
                round(ataque_avg, 1),
                round(defensa_avg, 1),
                round(regates_avg, 1),
                round(pases_avg, 1),
                round(comportamiento_avg, 1),
                round(minutos_percentil, 1),
                round(puntos_percentil, 1),
            ]
            labels = ['Ataque', 'Defensa', 'Regate', 'Pases', 'Comportamiento', 'Minutos', 'Fantasy']

        media_general = sum(radar_values) / len(radar_values) if radar_values else 0
        logger.info(
            "Radar generado para jugador %s (%s) en %s: %s",
            jugador_id, posicion, temporada, radar_values,
        )
        return Response({
            'status': 'success',
            'data': {
                'jugador_id': jugador.id,
                'jugador_nombre': f"{jugador.nombre} {jugador.apellido}",
                'temporada': temporada,
                'posicion': posicion,
                'radar_values': radar_values,
                'media_general': round(media_general, 2),
                'labels': labels,
            },
        })


# ── 2. BUSCAR ─────────────────────────────────────────────────────────────────

class BuscarView(APIView):
    """GET /api/buscar/?q=QUERY

    Full-text search over players and teams using Meilisearch.
    Requires at least 2 characters. Returns up to 5 combined results.
    """
    permission_classes = [AllowAny]

    def get(self, request):
        query = request.GET.get('q', '').strip()
        if len(query) < 2:
            return Response(
                {'status': 'error', 'message': 'Mínimo 2 caracteres requeridos', 'results': []},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not MEILISEARCH_AVAILABLE or not meilisearch_client:
            return Response(
                {
                    'status': 'error',
                    'message': 'Meilisearch no está disponible. Asegúrate de que esté corriendo en localhost:7700 y reinicia el servidor.',
                    'results': [],
                },
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        resultados = []

        try:
            # ── Jugadores ──────────────────────────────────────────────────
            search_body_jugador = {
                'query': {
                    'bool': {
                        'should': [
                            {'match_phrase_prefix': {'nombre_completo': {'query': query, 'boost': 10}}},
                            {'match_phrase_prefix': {'nombre': {'query': query, 'boost': 8}}},
                            {'match_phrase_prefix': {'apellido': {'query': query, 'boost': 8}}},
                            {'match': {'nombre_completo': {'query': query, 'fuzziness': 'AUTO', 'boost': 5}}},
                            {'match': {'nombre': {'query': query, 'fuzziness': 'AUTO', 'boost': 4}}},
                            {'match': {'apellido': {'query': query, 'fuzziness': 'AUTO', 'boost': 4}}},
                        ],
                        'minimum_should_match': 1,
                    }
                },
                'size': 10,
            }
            response = meilisearch_client.search(index='jugadores', body=search_body_jugador)
            for hit in response['hits']['hits']:
                src = hit['_source']
                try:
                    nombre = src.get('nombre', '')
                    apellido = src.get('apellido', '')
                    src_id = src.get('id')
                    if src_id and str(src_id).lstrip('-').isdigit():
                        jugador_pk = int(src_id)
                    else:
                        jugador_pk = (
                            Jugador.objects
                            .filter(nombre=nombre, apellido=apellido)
                            .values_list('id', flat=True)
                            .first()
                        )
                    if jugador_pk:
                        resultados.append({
                            'type': 'jugador',
                            'id': jugador_pk,
                            'nombre': f'{nombre} {apellido}',
                            'posicion': src.get('posicion', 'Desconocida'),
                            'url': f'/jugador/{jugador_pk}/',
                        })
                except Exception as exc:
                    logger.warning(f"Error procesando resultado de jugador: {exc}")

            # ── Equipos ────────────────────────────────────────────────────
            temporadas = Temporada.objects.all().order_by('-nombre')
            temporada_nombre = temporadas.first().nombre if temporadas.exists() else '25_26'

            search_body_equipo = {
                'query': {
                    'bool': {
                        'should': [
                            {'match_phrase_prefix': {'nombre': {'query': query, 'boost': 10}}},
                            {'match_phrase_prefix': {'estadio': {'query': query, 'boost': 5}}},
                            {'match': {'nombre': {'query': query, 'fuzziness': 'AUTO', 'boost': 5}}},
                            {'match': {'estadio': {'query': query, 'fuzziness': 'AUTO', 'boost': 2}}},
                        ],
                        'minimum_should_match': 1,
                    }
                },
                'size': 10,
            }
            response = meilisearch_client.search(index='equipos', body=search_body_equipo)
            for hit in response['hits']['hits']:
                src = hit['_source']
                resultados.append({
                    'type': 'equipo',
                    'id': src.get('id'),
                    'nombre': src.get('nombre'),
                    'url': f'/equipo/{src.get("nombre")}/{temporada_nombre}/',
                })

        except Exception as exc:
            logger.error(f"Error en búsqueda Meilisearch: {exc}", exc_info=True)
            return Response(
                {'status': 'error', 'message': f'Error en búsqueda: {exc}', 'results': []},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        return Response({'status': 'success', 'results': resultados[:5]})
