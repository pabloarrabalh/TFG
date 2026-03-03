"""
DRF API views – Menu / Home page data
Endpoints:
  GET /api/menu/
"""
import logging

from django.db.models import Avg, Q
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import (
    Temporada, Jornada, Calendario, ClasificacionJornada,
    Jugador, EquipoJugadorTemporada, PrediccionJugador,
)
from .views_utils import shield_name

logger = logging.getLogger(__name__)


# ── helpers ───────────────────────────────────────────────────────────────────

def _serialize_partido_calendario(calendario):
    """Serializa un objeto Calendario a dict para la API."""
    return {
        'id': calendario.id,
        'equipo_local': calendario.equipo_local.nombre,
        'equipo_visitante': calendario.equipo_visitante.nombre,
        'equipo_local_escudo': shield_name(calendario.equipo_local.nombre),
        'equipo_visitante_escudo': shield_name(calendario.equipo_visitante.nombre),
        'fecha': calendario.fecha.strftime('%Y-%m-%d') if calendario.fecha else None,
        'hora': str(calendario.hora) if calendario.hora else None,
        'jornada': calendario.jornada.numero_jornada if calendario.jornada else None,
    }


def _get_jugadores_destacados_con_predicciones(temporada, proxima_jornada):
    """
    Retorna jugadores destacados de la próxima jornada con predicciones y próximo rival.
    Agrupa por posición y retorna los mejores 3 por posición.
    """
    resultado = {}
    if not proxima_jornada or not temporada:
        return resultado

    posiciones = ['Portero', 'Defensa', 'Centrocampista', 'Delantero']

    predicciones = (
        PrediccionJugador.objects
        .filter(jornada=proxima_jornada)
        .select_related('jugador', 'jugador__equipos_temporada')
        .values('jugador_id', 'jugador__nombre', 'jugador__apellido')
        .annotate(pred_promedio=Avg('prediccion'))
        .order_by('-pred_promedio')
    )

    for posicion in posiciones:
        jugadores_por_posicion = []

        for pred in predicciones:
            jugador_id = pred['jugador_id']
            try:
                jugador = Jugador.objects.get(pk=jugador_id)
                ejt = EquipoJugadorTemporada.objects.filter(
                    jugador=jugador, temporada=temporada
                ).first()

                if not ejt or ejt.posicion != posicion:
                    continue

                proximo_rival = None
                calendario = Calendario.objects.filter(jornada=proxima_jornada).filter(
                    Q(equipo_local=ejt.equipo) | Q(equipo_visitante=ejt.equipo)
                ).first()

                if calendario:
                    proximo_rival = (
                        calendario.equipo_visitante.nombre
                        if calendario.equipo_local == ejt.equipo
                        else calendario.equipo_local.nombre
                    )

                jugadores_por_posicion.append({
                    'id': jugador.id,
                    'nombre': jugador.nombre,
                    'apellido': jugador.apellido,
                    'posicion': posicion,
                    'equipo': ejt.equipo.nombre,
                    'equipo_escudo': shield_name(ejt.equipo.nombre),
                    'dorsal': str(ejt.dorsal) if ejt.dorsal else '—',
                    'prediccion': round(float(pred['pred_promedio']), 2),
                    'proximo_rival': proximo_rival or '—',
                })
            except Exception as exc:
                logger.debug('Error procesando jugador %s: %s', jugador_id, exc)
                continue

        resultado[posicion] = jugadores_por_posicion[:3]

    return resultado


# ── view ──────────────────────────────────────────────────────────────────────

class MenuView(APIView):
    """GET /api/menu/"""

    def get(self, request):
        from datetime import datetime

        temporada = Temporada.objects.order_by('-nombre').first()
        empty = {
            'clasificacion_top': [],
            'partidos_proxima_jornada': [],
            'partidos_favoritos': [],
            'jornada_actual': None,
            'proxima_jornada': None,
            'jugadores_destacados_por_posicion': {},
        }
        if not temporada:
            return Response(empty)

        jornada_actual = (
            Jornada.objects.filter(temporada=temporada, numero_jornada=17).first()
            or Jornada.objects.filter(
                temporada=temporada, fecha_fin__gte=datetime.now()
            ).order_by('numero_jornada').first()
            or Jornada.objects.filter(temporada=temporada)
            .order_by('-numero_jornada')
            .exclude(numero_jornada=38)
            .first()
        )

        clasificacion_top = []
        if jornada_actual:
            qs = (
                ClasificacionJornada.objects
                .filter(temporada=temporada, jornada=jornada_actual)
                .order_by('posicion')[:5]
                .select_related('equipo')
            )
            for reg in qs:
                clasificacion_top.append({
                    'posicion': reg.posicion,
                    'equipo': reg.equipo.nombre,
                    'equipo_escudo': shield_name(reg.equipo.nombre),
                    'puntos': reg.puntos,
                })

        proxima_jornada = None
        partidos_proxima = []
        if jornada_actual:
            proxima_jornada = Jornada.objects.filter(
                temporada=temporada,
                numero_jornada=jornada_actual.numero_jornada + 1,
            ).first()
            if proxima_jornada:
                for p in (
                    Calendario.objects.filter(jornada=proxima_jornada)
                    .select_related('equipo_local', 'equipo_visitante')
                    .order_by('fecha', 'hora')
                ):
                    partidos_proxima.append(_serialize_partido_calendario(p))

        partidos_favoritos = []
        if request.user.is_authenticated and proxima_jornada:
            fav_ids = set(
                request.user.equipos_favoritos.values_list('equipo_id', flat=True)
            )
            if fav_ids:
                for p in (
                    Calendario.objects.filter(jornada=proxima_jornada)
                    .filter(
                        Q(equipo_local_id__in=fav_ids)
                        | Q(equipo_visitante_id__in=fav_ids)
                    )
                    .select_related('equipo_local', 'equipo_visitante')
                ):
                    partidos_favoritos.append(_serialize_partido_calendario(p))

        jugadores_destacados = _get_jugadores_destacados_con_predicciones(
            temporada, proxima_jornada
        )

        return Response({
            'clasificacion_top': clasificacion_top,
            'jornada_actual': {'numero': jornada_actual.numero_jornada} if jornada_actual else None,
            'proxima_jornada': {'numero': proxima_jornada.numero_jornada} if proxima_jornada else None,
            'partidos_proxima_jornada': partidos_proxima,
            'partidos_favoritos': partidos_favoritos,
            'jugadores_destacados_por_posicion': jugadores_destacados,
        })
