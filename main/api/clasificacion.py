"""
DRF API views – League Classification
Endpoints:
  GET /api/clasificacion/?temporada=25/26&jornada=17&equipo=&favoritos=true
"""
import logging

from django.db.models import Q, Sum, Count
from django.utils.timezone import now
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework import status
from rest_framework.permissions import AllowAny

from ..models import (
    Temporada, Jornada, Calendario, ClasificacionJornada,
    Equipo, EquipoJugadorTemporada, EstadisticasPartidoJugador, Partido,
)
from ..views.utils import shield_name, get_racha_detalles
from .menu import _serialize_partido_calendario

logger = logging.getLogger(__name__)


class ClasificacionView(APIView):
    """GET /api/clasificacion/"""
    permission_classes = [AllowAny]

    def get(self, request):
        try:
            temporada_display = request.GET.get('temporada', '25/26')
            jornada_num = request.GET.get('jornada')
            equipo_seleccionado = request.GET.get('equipo', '')
            mostrar_favoritos = request.GET.get('favoritos', '').lower() == 'true'

            temporada_nombre = temporada_display.replace('/', '_')
            try:
                temporada = Temporada.objects.get(nombre=temporada_nombre)
            except Temporada.DoesNotExist:
                temporada = Temporada.objects.order_by('-nombre').first()

            if not temporada:
                return Response({'error': 'No hay temporadas'}, status=status.HTTP_404_NOT_FOUND)

            temporadas = [
                {'nombre': t.nombre, 'display': t.nombre.replace('_', '/')}
                for t in Temporada.objects.order_by('-nombre')
            ]
            jornadas = [
                {'numero': j.numero_jornada}
                for j in Jornada.objects.filter(temporada=temporada).order_by('numero_jornada')
            ]
            equipos_disponibles = [{'nombre': e.nombre} for e in Equipo.objects.order_by('nombre')]

            # Determine which jornada to show
            jornada_obj = None
            if jornada_num:
                try:
                    jornada_obj = Jornada.objects.get(
                        temporada=temporada, numero_jornada=int(jornada_num)
                    )
                except (Jornada.DoesNotExist, ValueError):
                    # Si la jornada específica no existe, usa la actual
                    jornada_obj = (
                        Jornada.objects.filter(
                            temporada=temporada, fecha_fin__gte=now()
                        ).order_by('numero_jornada').first()
                        or Jornada.objects.filter(temporada=temporada).order_by('-numero_jornada').exclude(numero_jornada=38).first()
                    )
            else:
                # Sin jornada en parámetros: usa la jornada actual (que ya jugó)
                jornada_obj = (
                    Jornada.objects.filter(
                        temporada=temporada, fecha_fin__lt=now()
                    ).order_by('-numero_jornada').first()
                    or Jornada.objects.filter(temporada=temporada).order_by('-numero_jornada').exclude(numero_jornada=38).first()
                    or Jornada.objects.filter(temporada=temporada).order_by('numero_jornada').first()
                )

            clasificacion = []
            if jornada_obj:
                for reg in (
                    ClasificacionJornada.objects
                    .filter(temporada=temporada, jornada=jornada_obj)
                    .order_by('posicion')
                    .select_related('equipo')
                ):
                    try:
                        palabras = reg.equipo.nombre.split()
                        iniciales = ''.join(p[0].upper() for p in palabras)
                        clasificacion.append({
                            'posicion': reg.posicion,
                            'equipo': reg.equipo.nombre,
                            'equipo_escudo': shield_name(reg.equipo.nombre),
                            'iniciales': iniciales,
                            'puntos': reg.puntos,
                            'partidos_ganados': reg.partidos_ganados,
                            'partidos_empatados': reg.partidos_empatados,
                            'partidos_perdidos': reg.partidos_perdidos,
                            'goles_favor': reg.goles_favor,
                            'goles_contra': reg.goles_contra,
                            'diferencia_goles': reg.goles_favor - reg.goles_contra,
                            'racha_detalles': get_racha_detalles(reg.equipo, temporada, jornada_obj),
                        })
                    except Exception as exc:
                        logger.error('Error processing clasificacion: %s', exc)
                        continue

            # Filter by favourites / specific team
            if mostrar_favoritos and request.user.is_authenticated:
                try:
                    fav_ids = set(
                        request.user.equipos_favoritos.values_list('equipo_id', flat=True)
                    )
                    clasificacion = [
                        c for c in clasificacion
                        if any(
                            eq.id in fav_ids
                            for eq in Equipo.objects.filter(nombre=c['equipo'])
                        )
                    ]
                except Exception:
                    pass
            elif equipo_seleccionado:
                clasificacion = [
                    c for c in clasificacion
                    if c['equipo'].lower() == equipo_seleccionado.lower()
                ]

            # Partidos de la jornada
            partidos_jornada = []
            if jornada_obj:
                for p in (
                    Calendario.objects.filter(jornada=jornada_obj)
                    .select_related('equipo_local', 'equipo_visitante')
                    .order_by('fecha', 'hora')
                ):
                    try:
                        entry = _serialize_partido_calendario(p)
                        try:
                            partido_jugado = Partido.objects.get(
                                Q(
                                    equipo_local=p.equipo_local,
                                    equipo_visitante=p.equipo_visitante,
                                ) | Q(
                                    equipo_local=p.equipo_visitante,
                                    equipo_visitante=p.equipo_local,
                                ),
                                jornada=jornada_obj,
                                goles_local__isnull=False,
                            )
                            entry['jugado'] = True
                            entry['goles_local'] = partido_jugado.goles_local
                            entry['goles_visitante'] = partido_jugado.goles_visitante
                            entry['sucesos'] = self._build_sucesos(partido_jugado, temporada)
                        except Partido.DoesNotExist:
                            entry['jugado'] = False
                            entry['goles_local'] = None
                            entry['goles_visitante'] = None
                            entry['sucesos'] = self._empty_sucesos()
                        partidos_jornada.append(entry)
                    except Exception as exc:
                        logger.error('Error processing partido: %s', exc)
                        continue

            # Filter partidos
            if mostrar_favoritos and request.user.is_authenticated:
                try:
                    fav_ids = set(
                        request.user.equipos_favoritos.values_list('equipo_id', flat=True)
                    )
                    fav_nombres = set(
                        Equipo.objects.filter(id__in=fav_ids).values_list('nombre', flat=True)
                    )
                    partidos_jornada = [
                        p for p in partidos_jornada
                        if p['equipo_local'] in fav_nombres or p['equipo_visitante'] in fav_nombres
                    ]
                except Exception:
                    pass
            elif equipo_seleccionado:
                partidos_jornada = [
                    p for p in partidos_jornada
                    if (
                        p['equipo_local'].lower() == equipo_seleccionado.lower()
                        or p['equipo_visitante'].lower() == equipo_seleccionado.lower()
                    )
                ]

            favoritos_equipos = []
            if request.user.is_authenticated:
                try:
                    fav_ids = set(
                        request.user.equipos_favoritos.values_list('equipo_id', flat=True)
                    )
                    favoritos_equipos = [
                        {'nombre': e.nombre}
                        for e in Equipo.objects.filter(id__in=fav_ids)
                    ]
                except Exception:
                    pass

            return Response({
                'temporada': temporada_display,
                'temporadas': temporadas,
                'jornada_actual': jornada_obj.numero_jornada if jornada_obj else 1,
                'jornadas': jornadas,
                'clasificacion': clasificacion,
                'partidos_jornada': partidos_jornada,
                'equipos_disponibles': equipos_disponibles,
                'equipo_seleccionado': equipo_seleccionado,
                'favoritos_equipos': favoritos_equipos,
            })
        except Exception as exc:
            logger.error('Error in ClasificacionView: %s', exc, exc_info=True)
            return Response({'error': str(exc)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @staticmethod
    def _empty_sucesos():
        return {
            'goles_local': [],
            'goles_visitante': [],
            'amarillas_local': [],
            'amarillas_visitante': [],
            'rojas_local': [],
            'rojas_visitante': [],
        }

    @staticmethod
    def _build_sucesos(partido_jugado, temporada):
        goles_local, goles_visitante = [], []
        amarillas_local, amarillas_visitante = [], []
        rojas_local, rojas_visitante = [], []

        for stats in EstadisticasPartidoJugador.objects.filter(
            partido=partido_jugado
        ).select_related('jugador'):
            try:
                nombre = f'{stats.jugador.nombre} {stats.jugador.apellido}'.strip()
                minuto = stats.min_partido
                ejt = EquipoJugadorTemporada.objects.filter(
                    jugador=stats.jugador, temporada=temporada
                ).first()
                if not ejt:
                    continue
                eq = ejt.equipo

                if stats.gol_partido and stats.gol_partido > 0:
                    target = goles_local if eq == partido_jugado.equipo_local else goles_visitante
                    for _ in range(stats.gol_partido):
                        target.append({'nombre': nombre, 'minuto': minuto})

                if stats.amarillas and stats.amarillas > 0:
                    target = (
                        amarillas_local if eq == partido_jugado.equipo_local else amarillas_visitante
                    )
                    for _ in range(stats.amarillas):
                        target.append({'nombre': nombre, 'minuto': minuto})

                if stats.rojas and stats.rojas > 0:
                    target = (
                        rojas_local if eq == partido_jugado.equipo_local else rojas_visitante
                    )
                    for _ in range(stats.rojas):
                        target.append({'nombre': nombre, 'minuto': minuto})
            except Exception as exc:
                logger.error('Error processing stat: %s', exc)
                continue

        return {
            'goles_local': goles_local,
            'goles_visitante': goles_visitante,
            'amarillas_local': amarillas_local,
            'amarillas_visitante': amarillas_visitante,
            'rojas_local': rojas_local,
            'rojas_visitante': rojas_visitante,
        }
