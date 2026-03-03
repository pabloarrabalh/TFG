"""
DRF API views – Fantasy Plantilla (team builder)
Endpoints:
  GET  /api/mi-plantilla/?temporada=&jornada=
  GET  /api/mi-plantilla/jugadores/?pos=&q=&temporada=
  POST /api/plantilla/<id>/privacidad/
  POST /api/plantilla/<id>/predeterminada/
  GET  /api/plantillas/privacidad/
"""
import logging

from django.db.models import Q, Sum
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework import status

from .models import (
    Temporada, Jornada, Calendario, Equipo,
    EquipoJugadorTemporada, EstadisticasPartidoJugador, Plantilla,
)
from .views_utils import shield_name

logger = logging.getLogger(__name__)


class MiPlantillaView(APIView):
    """GET /api/mi-plantilla/?temporada=25/26&jornada=1"""

    def get(self, request):
        temporada_display = request.GET.get('temporada', '25/26')
        jornada_num = request.GET.get('jornada', '1')
        temporada_nombre = temporada_display.replace('/', '_')

        try:
            temporada = Temporada.objects.get(nombre=temporada_nombre)
        except Temporada.DoesNotExist:
            temporada = Temporada.objects.order_by('-nombre').first()

        if not temporada:
            return Response({'error': 'No hay temporadas disponibles'}, status=status.HTTP_404_NOT_FOUND)

        jornadas_qs = Jornada.objects.filter(temporada=temporada).order_by('numero_jornada')
        jornadas = [j.numero_jornada for j in jornadas_qs]
        temporadas_list = [
            t.nombre.replace('_', '/') for t in Temporada.objects.order_by('-nombre')
        ]

        try:
            jornada_obj = Jornada.objects.get(temporada=temporada, numero_jornada=int(jornada_num))
        except (Jornada.DoesNotExist, ValueError):
            jornada_obj = jornadas_qs.first()
            jornada_num = jornada_obj.numero_jornada if jornada_obj else 1

        jugadores_disponibles = []
        for ejt in EquipoJugadorTemporada.objects.filter(
            temporada=temporada
        ).select_related('jugador', 'equipo'):
            stats = EstadisticasPartidoJugador.objects.filter(
                jugador=ejt.jugador, partido__jornada__temporada=temporada
            ).aggregate(pts=Sum('puntos_fantasy'))
            jugadores_disponibles.append({
                'id': ejt.jugador.id,
                'nombre': ejt.jugador.nombre,
                'apellido': ejt.jugador.apellido,
                'posicion': ejt.posicion or ejt.jugador.get_posicion_mas_frecuente() or '',
                'equipo': ejt.equipo.nombre,
                'dorsal': ejt.dorsal,
                'puntos_fantasy': float(stats['pts'] or 0),
            })

        proximo_partido = None
        if jornada_obj:
            next_jornada = Jornada.objects.filter(
                temporada=temporada,
                numero_jornada__gt=jornada_obj.numero_jornada,
            ).order_by('numero_jornada').first()
            if next_jornada:
                next_p = (
                    Calendario.objects.filter(jornada=next_jornada)
                    .order_by('fecha', 'hora')
                    .first()
                )
                if next_p:
                    proximo_partido = {
                        'jornada': next_jornada.numero_jornada,
                        'rival': (
                            next_p.equipo_visitante.nombre
                            if next_p.equipo_local.nombre == 'Tu Equipo'
                            else next_p.equipo_local.nombre
                        ),
                        'es_local': next_p.equipo_local.nombre == 'Tu Equipo',
                        'fecha': next_p.fecha.strftime('%Y-%m-%d') if next_p.fecha else None,
                        'hora': str(next_p.hora) if next_p.hora else None,
                    }

        return Response({
            'temporada': temporada_display,
            'temporadas': temporadas_list,
            'jornada': jornada_num,
            'jornadas': jornadas,
            'jugadores_disponibles': jugadores_disponibles,
            'proximoPartido': proximo_partido,
            'plantilla': [],
        })


class MiPlantillaJugadoresView(APIView):
    """GET /api/mi-plantilla/jugadores/?pos=&q=&temporada="""

    def get(self, request):
        if not request.user.is_authenticated:
            return Response({'error': 'No autenticado'}, status=status.HTTP_401_UNAUTHORIZED)

        pos = request.GET.get('pos', '')
        q = request.GET.get('q', '').strip()
        temporada_display = request.GET.get('temporada', '25/26')
        temporada_nombre = temporada_display.replace('/', '_')

        try:
            temporada = Temporada.objects.get(nombre=temporada_nombre)
        except Temporada.DoesNotExist:
            temporada = Temporada.objects.order_by('-nombre').first()

        qs = EquipoJugadorTemporada.objects.filter(
            temporada=temporada
        ).select_related('jugador', 'equipo')
        if pos:
            qs = qs.filter(posicion__icontains=pos)
        if q:
            qs = qs.filter(
                Q(jugador__nombre__icontains=q) | Q(jugador__apellido__icontains=q)
            )

        result = []
        for ejt in qs.order_by('jugador__apellido')[:50]:
            stats = EstadisticasPartidoJugador.objects.filter(
                jugador=ejt.jugador, partido__jornada__temporada=temporada
            ).aggregate(pts=Sum('puntos_fantasy'))
            result.append({
                'id': ejt.jugador.id,
                'nombre': ejt.jugador.nombre,
                'apellido': ejt.jugador.apellido,
                'posicion': ejt.posicion or '',
                'equipo': ejt.equipo.nombre,
                'equipo_escudo': shield_name(ejt.equipo.nombre),
                'dorsal': ejt.dorsal,
                'puntos_fantasy': float(stats['pts'] or 0),
            })

        return Response({'jugadores': result})


class TogglePrivacidadPlantillaView(APIView):
    """POST /api/plantilla/<plantilla_id>/privacidad/"""

    def post(self, request, plantilla_id):
        if not request.user.is_authenticated:
            return Response({'error': 'No autenticado'}, status=status.HTTP_401_UNAUTHORIZED)
        try:
            plantilla = Plantilla.objects.get(id=plantilla_id, usuario=request.user)
            nueva = 'privada' if plantilla.privacidad == 'publica' else 'publica'
            plantilla.privacidad = nueva
            plantilla.save()
            return Response({'status': 'ok', 'privacidad': nueva})
        except Exception as exc:
            return Response({'error': str(exc)}, status=status.HTTP_400_BAD_REQUEST)


class SetPlantillaPredeterminadaView(APIView):
    """POST /api/plantilla/<plantilla_id>/predeterminada/"""

    def post(self, request, plantilla_id):
        if not request.user.is_authenticated:
            return Response({'error': 'No autenticado'}, status=status.HTTP_401_UNAUTHORIZED)
        try:
            plantilla = Plantilla.objects.get(id=plantilla_id, usuario=request.user)
            Plantilla.objects.filter(usuario=request.user).update(predeterminada=False)
            plantilla.predeterminada = True
            plantilla.save()
            return Response({'status': 'ok', 'plantilla_id': plantilla_id})
        except Exception as exc:
            if 'DoesNotExist' in type(exc).__name__:
                return Response({'error': 'Plantilla no encontrada'}, status=status.HTTP_404_NOT_FOUND)
            return Response({'error': str(exc)}, status=status.HTTP_400_BAD_REQUEST)


class MisPlantillasPrivacidadView(APIView):
    """GET /api/plantillas/privacidad/"""

    def get(self, request):
        if not request.user.is_authenticated:
            return Response({'error': 'No autenticado'}, status=status.HTTP_401_UNAUTHORIZED)
        try:
            plantillas = Plantilla.objects.filter(usuario=request.user).values(
                'id', 'nombre', 'privacidad', 'predeterminada'
            )
            return Response({'plantillas': list(plantillas)})
        except Exception as exc:
            return Response({'error': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
