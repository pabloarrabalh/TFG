"""
DRF API – Plantilla Notificaciones
Endpoints:
  GET /api/plantilla-notificaciones/<jornada_num>/
"""
import logging

from django.db.models import Q, Sum
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated

from ..models import (
    Plantilla, EstadisticasPartidoJugador, Jornada, Temporada, Notificacion
)

logger = logging.getLogger(__name__)


class PlantillaNotificacionesView(APIView):
    """GET /api/plantilla-notificaciones/<jornada_num>/"""
    permission_classes = [IsAuthenticated]

    def get(self, request, jornada_num):
        """Obtiene los eventos (goles, tarjetas, asistencias) de los jugadores de la plantilla."""
        try:
            logger.info(f'[PlantillaNotif] GET jornada={jornada_num}, user={request.user.username}')
            
            # Obtener plantilla predeterminada del usuario
            plantilla = (
                Plantilla.objects.filter(usuario=request.user, predeterminada=True).first()
                or Plantilla.objects.filter(usuario=request.user).order_by('-fecha_modificada').first()
            )
            logger.info(f'[PlantillaNotif] plantilla={plantilla}')
            
            if not plantilla:
                logger.info('[PlantillaNotif] No plantilla found')
                return Response({'eventos': []})
            
            # Obtener IDs de jugadores en alineación (sin suplentes)
            alineacion = plantilla.alineacion or {}
            jugador_ids = []
            for posicion in ['Portero', 'Defensa', 'Centrocampista', 'Delantero']:
                if posicion in alineacion:
                    for j in (alineacion[posicion] or []):
                        if j and j.get('id'):
                            jugador_ids.append(j['id'])
            
            logger.info(f'[PlantillaNotif] jugador_ids={jugador_ids}')
            if not jugador_ids:
                logger.info('[PlantillaNotif] No jugadores en alineacion')
                return Response({'eventos': []})
            
            # Obtener temporada actual
            temporada = Temporada.objects.filter(nombre='25_26').first() or Temporada.objects.order_by('-nombre').first()
            logger.info(f'[PlantillaNotif] temporada={temporada}')
            if not temporada:
                return Response({'eventos': []})
            
            # Obtener jornada
            try:
                jornada = Jornada.objects.get(numero_jornada=jornada_num, temporada=temporada)
            except Jornada.DoesNotExist:
                logger.info(f'[PlantillaNotif] Jornada {jornada_num} not found')
                return Response({'eventos': []})
            
            logger.info(f'[PlantillaNotif] jornada={jornada}')
            
            # Obtener estadísticas
            stats = EstadisticasPartidoJugador.objects.filter(
                jugador_id__in=jugador_ids,
                partido__jornada=jornada
            ).select_related('jugador', 'partido')
            
            logger.info(f'[PlantillaNotif] stats count={stats.count()}')
            
            eventos = []
            seen = set()

            def _get_equipo(stat):
                """Devuelve el nombre del equipo del jugador en ese partido."""
                jt = stat.jugador.equipos_temporada.filter(temporada=temporada).first()
                if jt and jt.equipo:
                    return jt.equipo.nombre
                return stat.partido.equipo_local.nombre  # fallback

            for stat in stats:
                # Goles
                if stat.gol_partido and stat.gol_partido > 0:
                    key = f"{stat.jugador_id}_gol"
                    if key not in seen:
                        logger.info(f'[PlantillaNotif] evento gol: {stat.jugador.nombre}')
                        eventos.append({
                            'jugador_id': stat.jugador_id,
                            'jugador_nombre': stat.jugador.nombre,
                            'jugador_apellido': stat.jugador.apellido,
                            'evento': 'gol',
                            'cantidad': stat.gol_partido,
                            'equipo': _get_equipo(stat),
                        })
                        seen.add(key)

                # Tarjeta amarilla
                if stat.amarillas and stat.amarillas > 0:
                    key = f"{stat.jugador_id}_tarjeta_amarilla"
                    if key not in seen:
                        logger.info(f'[PlantillaNotif] evento tarjeta_amarilla: {stat.jugador.nombre}')
                        eventos.append({
                            'jugador_id': stat.jugador_id,
                            'jugador_nombre': stat.jugador.nombre,
                            'jugador_apellido': stat.jugador.apellido,
                            'evento': 'tarjeta_amarilla',
                            'cantidad': stat.amarillas,
                            'equipo': _get_equipo(stat),
                        })
                        seen.add(key)

                # Tarjeta roja
                if stat.rojas and stat.rojas > 0:
                    key = f"{stat.jugador_id}_tarjeta_roja"
                    if key not in seen:
                        logger.info(f'[PlantillaNotif] evento tarjeta_roja: {stat.jugador.nombre}')
                        eventos.append({
                            'jugador_id': stat.jugador_id,
                            'jugador_nombre': stat.jugador.nombre,
                            'jugador_apellido': stat.jugador.apellido,
                            'evento': 'tarjeta_roja',
                            'cantidad': stat.rojas,
                            'equipo': _get_equipo(stat),
                        })
                        seen.add(key)

                # Asistencia
                if stat.asist_partido and stat.asist_partido > 0:
                    key = f"{stat.jugador_id}_asistencia"
                    if key not in seen:
                        logger.info(f'[PlantillaNotif] evento asistencia: {stat.jugador.nombre}')
                        eventos.append({
                            'jugador_id': stat.jugador_id,
                            'jugador_nombre': stat.jugador.nombre,
                            'jugador_apellido': stat.jugador.apellido,
                            'evento': 'asistencia',
                            'cantidad': stat.asist_partido,
                            'equipo': _get_equipo(stat),
                        })
                        seen.add(key)
            
            logger.info(f'[PlantillaNotif] total eventos={len(eventos)}')
            
            # Agrupar eventos por tipo para pluralizaciones correctas
            eventos_por_tipo = {}
            for evento in eventos:
                tipo = evento['evento']
                if tipo not in eventos_por_tipo:
                    eventos_por_tipo[tipo] = []
                eventos_por_tipo[tipo].append(evento)
            
            # Crear notificaciones si el usuario lo tiene activado
            prefs = getattr(getattr(request.user, 'profile', None), 'preferencias_notificaciones', 'none')
            if prefs in ('all', 'events') and eventos:
                for tipo_evento, eventos_tipo in eventos_por_tipo.items():
                    # Construir lista de jugadores
                    nombres = [f"{e['jugador_nombre']} {e['jugador_apellido']}" for e in eventos_tipo]
                    
                    # Determinar singular/plural
                    es_plural = len(nombres) > 1
                    jugadores_str = ", ".join(nombres)
                    
                    # Construir título según tipo
                    if tipo_evento == 'gol':
                        verbo = "han marcado" if es_plural else "ha marcado"
                        titulo = f"¡{jugadores_str} {verbo} en la jornada {jornada_num}!"
                    elif tipo_evento == 'asistencia':
                        verbo = "han asistido" if es_plural else "ha asistido"
                        titulo = f"¡{jugadores_str} {verbo} en la jornada {jornada_num}!"
                    elif tipo_evento == 'tarjeta_roja':
                        verbo = "han sido expulsados" if es_plural else "ha sido expulsado"
                        titulo = f"¡{jugadores_str} {verbo} en la jornada {jornada_num}!"
                    elif tipo_evento == 'tarjeta_amarilla':
                        verbo = "han recibido" if es_plural else "ha recibido"
                        titulo = f"¡{jugadores_str} {verbo} tarjeta amarilla en la jornada {jornada_num}!"
                    else:
                        titulo = f"📢 {jugadores_str}"
                    
                    # Verificar si ya existe (por tipo, no por jugador)
                    ya_existe = Notificacion.objects.filter(
                        usuario=request.user, tipo='evento_jugador',
                        datos__jornada=jornada_num, datos__evento=tipo_evento,
                    ).exists()
                    if ya_existe:
                        continue
                    
                    # Crear notificación única para el tipo de evento (sin mostrar equipo)
                    Notificacion.objects.create(
                        usuario=request.user, tipo='evento_jugador',
                        titulo=titulo,
                        mensaje='',
                        datos={'jornada': jornada_num, 'evento': tipo_evento, 'jugador_ids': [e['jugador_id'] for e in eventos_tipo]},
                    )

            return Response({'eventos': eventos})
        
        except Exception as exc:
            logger.error(f'PlantillaNotificaciones error: {exc}')
            return Response({'eventos': []})
