
from django.db.models import Q, Sum
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated

from ..models import *


class PlantillaNotificacionesView(APIView):
    """GET /api/plantilla-notificaciones/<jornada_num>/"""
    permission_classes = [IsAuthenticated]

    def get(self, request, jornada_num):
        try:
            plantilla = (Plantilla.objects.filter(usuario=request.user, predeterminada=True).first() or Plantilla.objects.filter(usuario=request.user).order_by('-fecha_modificada').first())

            if not plantilla:
                return Response({'eventos': []})
            
            alineacion = plantilla.alineacion or {}
            jugador_ids = []
            for posicion in ['Portero', 'Defensa', 'Centrocampista', 'Delantero']:
                if posicion in alineacion:
                    for j in (alineacion[posicion] or []):
                        if j and j.get('id'):
                            jugador_ids.append(j['id'])
            
            if not jugador_ids:
                return Response({'eventos': []})
            
            temporada = Temporada.objects.filter(nombre='25_26').first() or Temporada.objects.order_by('-nombre').first()
            if not temporada:
                return Response({'eventos': []})
            
            try:
                jornada = Jornada.objects.get(numero_jornada=jornada_num, temporada=temporada)
            except Jornada.DoesNotExist:
                return Response({'eventos': []})

            stats = EstadisticasPartidoJugador.objects.filter(jugador_id__in=jugador_ids,partido__jornada=jornada).select_related('jugador', 'partido')

            eventos = []
            seen = set()

            def _get_equipo(stat):
                jt = stat.jugador.equipos_temporada.filter(temporada=temporada).first()
                if jt and jt.equipo:
                    return jt.equipo.nombre
                return stat.partido.equipo_local.nombre  

            for stat in stats:
                if stat.gol_partido and stat.gol_partido > 0:
                    key = f"{stat.jugador_id}_gol"
                    if key not in seen:
                        eventos.append({
                            'jugador_id': stat.jugador_id,
                            'jugador_nombre': stat.jugador.nombre,
                            'jugador_apellido': stat.jugador.apellido,
                            'evento': 'gol',
                            'cantidad': stat.gol_partido,
                            'equipo': _get_equipo(stat),
                        })
                        seen.add(key)

                if stat.amarillas and stat.amarillas > 0:
                    key = f"{stat.jugador_id}_tarjeta_amarilla"
                    if key not in seen:
                        eventos.append({
                            'jugador_id': stat.jugador_id,
                            'jugador_nombre': stat.jugador.nombre,
                            'jugador_apellido': stat.jugador.apellido,
                            'evento': 'tarjeta_amarilla',
                            'cantidad': stat.amarillas,
                            'equipo': _get_equipo(stat),
                        })
                        seen.add(key)

                if stat.rojas and stat.rojas > 0:
                    key = f"{stat.jugador_id}_tarjeta_roja"
                    if key not in seen:
                        eventos.append({
                            'jugador_id': stat.jugador_id,
                            'jugador_nombre': stat.jugador.nombre,
                            'jugador_apellido': stat.jugador.apellido,
                            'evento': 'tarjeta_roja',
                            'cantidad': stat.rojas,
                            'equipo': _get_equipo(stat),
                        })
                        seen.add(key)

                if stat.asist_partido and stat.asist_partido > 0:
                    key = f"{stat.jugador_id}_asistencia"
                    if key not in seen:
                        eventos.append({
                            'jugador_id': stat.jugador_id,
                            'jugador_nombre': stat.jugador.nombre,
                            'jugador_apellido': stat.jugador.apellido,
                            'evento': 'asistencia',
                            'cantidad': stat.asist_partido,
                            'equipo': _get_equipo(stat),
                        })
                        seen.add(key)
            
            eventos_por_tipo = {}
            for evento in eventos:
                tipo = evento['evento']
                if tipo not in eventos_por_tipo:
                    eventos_por_tipo[tipo] = []
                eventos_por_tipo[tipo].append(evento)
            
            prefs = getattr(getattr(request.user, 'profile', None), 'preferencias_notificaciones', 'none')
            if prefs in ('all', 'events') and eventos:
                for tipo_evento, eventos_tipo in eventos_por_tipo.items():
                    nombres = [f"{e['jugador_nombre']} {e['jugador_apellido']}" for e in eventos_tipo]
                    
                    es_plural = len(nombres) > 1
                    jugadores_str = ", ".join(nombres)
                    
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
                        titulo = f" {jugadores_str}"
                    
                    ya_existe = Notificacion.objects.filter(usuario=request.user, tipo='evento_jugador',datos__jornada=jornada_num, datos__evento=tipo_evento,).exists()
                    if ya_existe:
                        continue
                    
                    Notificacion.objects.create(
                        usuario=request.user, tipo='evento_jugador',
                        titulo=titulo,
                        mensaje='',
                        datos={'jornada': jornada_num, 'evento': tipo_evento, 'jugador_ids': [e['jugador_id'] for e in eventos_tipo]},
                    )

            return Response({'eventos': eventos})
        
        except Exception:
            return Response({'eventos': []})
