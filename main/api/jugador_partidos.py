"""
API endpoint para obtener últimos partidos de un jugador
GET /api/jugador_partidos/?jugador_id=123&jornada_actual=12
"""
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import AllowAny
from ..models import (
    Jugador, Jornada, Partido, EstadisticasPartidoJugador, 
    EquipoJugadorTemporada, Temporada
)


class JugadorPartidosView(APIView):
    """GET /api/jugador_partidos/?jugador_id=123&jornada_actual=12"""
    permission_classes = [AllowAny]

    def get(self, request):
        jugador_id = request.GET.get('jugador_id')
        jornada_actual = request.GET.get('jornada_actual')
        
        if not jugador_id or not jornada_actual:
            return Response({'error': 'Parámetros requeridos', 'partidos': []}, status=200)
        
        try:
            jugador = Jugador.objects.get(id=jugador_id)
            jornada_num = int(jornada_actual)
            # Obtener temporada actual
            temporada = Temporada.objects.order_by('-nombre').first()
        except (Jugador.DoesNotExist, ValueError, AttributeError):
            return Response({'jugador': {'id': jugador_id}, 'partidos': []}, status=200)
        
        if not temporada:
            return Response({'jugador': {'id': jugador_id}, 'partidos': []}, status=200)
        
        try:
            # Obtener últimos 5 partidos del jugador (sin unir con EquipoJugadorTemporada)
            ultimos_partidos = (
                EstadisticasPartidoJugador.objects
                .filter(jugador=jugador, partido__jornada__temporada=temporada)
                .select_related('partido', 'partido__equipo_local', 'partido__equipo_visitante', 'partido__jornada')
                .order_by('-partido__jornada__numero_jornada')[:5]
            )
            
            # Obtener equipo actual del jugador
            ejt = (
                EquipoJugadorTemporada.objects
                .filter(jugador=jugador, temporada=temporada)
                .select_related('equipo')
                .first()
            )
            
            partidos_info = []
            for stat in ultimos_partidos:
                p = stat.partido
                
                # Determinar rival
                if ejt:
                    jugador_equipo_id = ejt.equipo_id
                    rival_nombre = (
                        p.equipo_visitante.nombre if p.equipo_local_id == jugador_equipo_id
                        else p.equipo_local.nombre
                    )
                else:
                    rival_nombre = 'TBD'
                
                # Determinar fecha del partido
                fecha_str = None
                if p.fecha_partido:
                    fecha_str = p.fecha_partido.strftime('%d/%m')
                
                partidos_info.append({
                    'jornada': p.jornada.numero_jornada,
                    'rival': rival_nombre,
                    'minutos': stat.min_partido or 0,
                    'puntos': stat.puntos_fantasy if stat.puntos_fantasy and stat.puntos_fantasy > 0 else None,
                    'fecha': fecha_str,
                })
            
            return Response({
                'jugador': {
                    'id': jugador.id,
                    'nombre': jugador.nombre,
                    'apellido': jugador.apellido,
                },
                'partidos': partidos_info[:5],  # Últimos 5
            }, status=200)
        except Exception as e:
            # En caso de cualquier otro error, devolver lista vacía
            return Response({
                'jugador': {'id': jugador_id},
                'partidos': []
            }, status=200)
