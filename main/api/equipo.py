from datetime import datetime, time
from difflib import SequenceMatcher

from django.db.models import Q, Sum, Count, Max
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework import status
from rest_framework.permissions import AllowAny

from .common import get_temporada_by_display, parse_int, temporada_display_from_name
from ..models import *
from ..views.utils import *


class EquipoListView(APIView):
    """GET /api/equipos/"""
    permission_classes = [AllowAny]

    def get(self, request):
        favoritos_ids = set()
        if request.user.is_authenticated:
            try:
                favoritos_ids = set(request.user.equipos_favoritos.values_list('equipo_id', flat=True))
            except Exception:
                pass

        temporada = Temporada.objects.order_by('-nombre').first()

        counts_current = {}
        if temporada:
            for row in (
                EquipoJugadorTemporada.objects
                .filter(temporada=temporada)
                .values('equipo_id')
                .annotate(cnt=Count('id'))
            ):
                counts_current[row['equipo_id']] = row['cnt']

        latest_season_map = {}
        for row in ( EquipoJugadorTemporada.objects.values('equipo_id').annotate(latest=Max('temporada__nombre'))
        ):
            latest_season_map[row['equipo_id']] = row['latest']

        result = []
        for eq in Equipo.objects.order_by('nombre'):
            jugadores_count = counts_current.get(eq.id, 0)
            suggested_temporada = None
            if jugadores_count == 0:
                latest = latest_season_map.get(eq.id)
                if latest:
                    suggested_temporada = latest.replace('_', '/')
            result.append({
                'id': eq.id,
                'nombre': eq.nombre,
                'escudo': shield_name(eq.nombre),
                'estadio': eq.estadio or '',
                'jugadores_count': jugadores_count,
                'es_favorito': eq.id in favoritos_ids,
                'suggested_temporada': suggested_temporada,
            })

        return Response({'equipos': result})


class EquipoDetailView(APIView):
    """GET /api/equipo/<equipo_nombre>/?temporada=25/26&jornada=N"""
    permission_classes = [AllowAny]

    def get(self, request, equipo_nombre):
        temporada_display = request.GET.get('temporada', '25/26')
        jornada_param = request.GET.get('jornada')

        try:
            equipo = Equipo.objects.get(nombre=equipo_nombre)
        except Equipo.DoesNotExist:
            return Response({'error': 'Equipo no encontrado'}, status=status.HTTP_404_NOT_FOUND)

        temporadas = Temporada.objects.all().order_by('-nombre')
        temporadas_display = [
            {'nombre': t.nombre, 'display': t.nombre.replace('_', '/')} for t in temporadas
        ]

        temporada = get_temporada_by_display(temporada_display)
        if not temporada:
            temporada = temporadas.first()
        if temporada:
            temporada_display = temporada_display_from_name(temporada.nombre)

        jornadas_temp = Jornada.objects.filter(temporada=temporada).order_by('numero_jornada')
        jornadas_disponibles = [{'numero': j.numero_jornada} for j in jornadas_temp]

        ultima_jornada_clasificacion = (
            Jornada.objects.filter(temporada=temporada, clasificacionjornada__isnull=False).last()
        )

        jornada_actual = None
        if jornada_param:
            jornada_actual = parse_int(jornada_param, default=None, min_value=1)

        if jornada_actual is None:
            jornada_actual = (
                ultima_jornada_clasificacion.numero_jornada
                if ultima_jornada_clasificacion
                else 1
            )

        jornada_min = 1
        jornada_max = 38

        try:
            jornada_actual_obj = Jornada.objects.get(
                temporada=temporada, numero_jornada=jornada_actual
            )
        except Jornada.DoesNotExist:
            jornada_actual_obj = ultima_jornada_clasificacion

        jugadores_equipo_temp = (EquipoJugadorTemporada.objects.filter(equipo=equipo, temporada=temporada).select_related('jugador').order_by('dorsal'))

        jugadores_agrupados = {}
        puntos_dorsal_cero = {}

        for eq_jug_temp in jugadores_equipo_temp:
            stats_query = EstadisticasPartidoJugador.objects.filter(
                jugador=eq_jug_temp.jugador,
                partido__jornada__temporada=temporada,
            )
            if jornada_actual:
                stats_query = stats_query.filter(
                    partido__jornada__numero_jornada__lte=jornada_actual
                )
            valid_stats = stats_query.exclude(puntos_fantasy__gt=40)

            total_goles = valid_stats.aggregate(Sum('gol_partido'))['gol_partido__sum'] or 0
            total_asistencias = (valid_stats.aggregate(Sum('asist_partido'))['asist_partido__sum'] or 0)
            total_puntos = (valid_stats.aggregate(Sum('puntos_fantasy'))['puntos_fantasy__sum'] or 0)
            partidos_jugados = valid_stats.count()
            total_minutos = valid_stats.aggregate(Sum('min_partido'))['min_partido__sum'] or 0

            if eq_jug_temp.dorsal == 0 and total_puntos <= 0:
                nombre_completo = (
                    f'{eq_jug_temp.jugador.nombre} {eq_jug_temp.jugador.apellido}'.strip()
                )
                puntos_dorsal_cero[nombre_completo] = {'puntos': total_puntos}
                continue

            # Solo los que hayan jugado
            if partidos_jugados == 0 and total_minutos == 0:
                continue

            posicion_frecuente = (valid_stats.values('posicion').annotate(count=Count('id')).order_by('-count').first())

            jug_id = eq_jug_temp.jugador.id
            if jug_id not in jugadores_agrupados:
                jugadores_agrupados[jug_id] = {
                    'obj': eq_jug_temp,
                    'total_goles': total_goles,
                    'total_asistencias': total_asistencias,
                    'total_puntos': total_puntos,
                    'partidos_stats': partidos_jugados,
                    'total_minutos': total_minutos,
                    'posicion': posicion_frecuente['posicion'] if posicion_frecuente else None,
                    'nombre': eq_jug_temp.jugador.nombre,
                    'apellido': eq_jug_temp.jugador.apellido,
                }
            else:
                jugadores_agrupados[jug_id]['total_puntos'] += total_puntos
                jugadores_agrupados[jug_id]['total_goles'] += total_goles
                jugadores_agrupados[jug_id]['total_asistencias'] += total_asistencias

        if len(jugadores_agrupados) < 10:
            jugadores_con_stats = (EstadisticasPartidoJugador.objects.filter(partido__jornada__temporada=temporada)
                .filter(Q(partido__equipo_local=equipo) | Q(partido__equipo_visitante=equipo))
                .values_list('jugador_id', flat=True)
                .distinct()
            )
            for jug_id in jugadores_con_stats:
                if jug_id in jugadores_agrupados:
                    continue
                jugador = Jugador.objects.filter(id=jug_id).first()
                if not jugador:
                    continue
                sq = EstadisticasPartidoJugador.objects.filter(
                    jugador=jugador, partido__jornada__temporada=temporada
                )
                if jornada_actual:
                    sq = sq.filter(partido__jornada__numero_jornada__lte=jornada_actual)
                vsq = sq.exclude(puntos_fantasy__gt=40)
                total_goles = vsq.aggregate(Sum('gol_partido'))['gol_partido__sum'] or 0
                total_asistencias = vsq.aggregate(Sum('asist_partido'))['asist_partido__sum'] or 0
                total_puntos = vsq.aggregate(Sum('puntos_fantasy'))['puntos_fantasy__sum'] or 0
                partidos_jugados = vsq.count()
                total_minutos = vsq.aggregate(Sum('min_partido'))['min_partido__sum'] or 0
                if total_puntos > 0 or partidos_jugados > 0:
                    pf = vsq.values('posicion').annotate(count=Count('id')).order_by('-count').first()
                    jugadores_agrupados[jugador.id] = {
                        'obj': None,
                        'total_goles': total_goles,
                        'total_asistencias': total_asistencias,
                        'total_puntos': total_puntos,
                        'partidos_stats': partidos_jugados,
                        'total_minutos': total_minutos,
                        'posicion': pf['posicion'] if pf else None,
                        'nombre': jugador.nombre,
                        'apellido': jugador.apellido,
                    }

        # dorsal 0
        def _similitud(n1, n2):
            return SequenceMatcher(None, n1.lower(), n2.lower()).ratio()

        for nombre_d0, datos_d0 in puntos_dorsal_cero.items():
            mejor_coincidencia = None
            mejor_sim = 0.6
            for jug_id, datos_prin in jugadores_agrupados.items():
                nombre_prin = f"{datos_prin['nombre']} {datos_prin['apellido']}".strip()
                sim = _similitud(nombre_d0, nombre_prin)
                if sim > mejor_sim:
                    mejor_sim = sim
                    mejor_coincidencia = jug_id
            if mejor_coincidencia:
                jugadores_agrupados[mejor_coincidencia]['total_puntos'] += datos_d0['puntos']

        jugadores = []
        for datos in jugadores_agrupados.values():
            eq_jug_temp = datos['obj']
            if eq_jug_temp is None:
                continue
            jugadores.append({
                'jugador_id': eq_jug_temp.jugador.id,
                'id': eq_jug_temp.jugador.id,
                'nombre': eq_jug_temp.jugador.nombre,
                'apellido': eq_jug_temp.jugador.apellido,
                'dorsal': eq_jug_temp.dorsal,
                'posicion': datos['posicion'] or eq_jug_temp.posicion or '',
                'nacionalidad': eq_jug_temp.jugador.nacionalidad or '',
                'goles': datos['total_goles'],
                'asistencias': datos['total_asistencias'],
                'puntos_fantasy': datos['total_puntos'],
                'partidos': datos['partidos_stats'],
                'minutos': datos['total_minutos'],
            })

        top_3_puntos = sorted(jugadores, key=lambda x: x['puntos_fantasy'], reverse=True)[:3]
        top_3_minutos = sorted(jugadores, key=lambda x: x['minutos'], reverse=True)[:3]

        clasificacion_actual = (
            ClasificacionJornada.objects.filter(equipo=equipo, temporada=temporada,jornada__numero_jornada__lte=jornada_actual,)
            .order_by('-jornada__numero_jornada')
            .first()
        )

        goles_equipo_favor = clasificacion_actual.goles_favor if clasificacion_actual else 0
        goles_equipo_contra = clasificacion_actual.goles_contra if clasificacion_actual else 0
        racha_actual_detalles = (get_racha_detalles(equipo, temporada, jornada_actual_obj) if jornada_actual_obj else [])

        #P´roximo partido
        proximo_partido = None
        rival_info = None

        if jornada_actual and jornada_actual < jornada_max:
            proximo_encontrado = None
            for offset in range(1, (jornada_max - jornada_actual) + 1):
                intento_num = jornada_actual + offset
                p_cal = (Calendario.objects.filter(jornada__temporada=temporada,jornada__numero_jornada=intento_num,)
                    .filter(Q(equipo_local=equipo) | Q(equipo_visitante=equipo))
                    .first()
                )
                if p_cal:
                    proximo_encontrado = ('calendario', p_cal)
                    break
                p_partido = (Partido.objects.filter(jornada__temporada=temporada,jornada__numero_jornada=intento_num,)
                    .filter(Q(equipo_local=equipo) | Q(equipo_visitante=equipo))
                    .select_related('equipo_local', 'equipo_visitante', 'jornada')
                    .first()
                )
                if p_partido:
                    proximo_encontrado = ('partido', p_partido)
                    break

            if proximo_encontrado:
                tipo_fuente, pc = proximo_encontrado
                if pc.equipo_local == equipo:
                    rival = pc.equipo_visitante
                    es_local = True
                else:
                    rival = pc.equipo_local
                    es_local = False

                if tipo_fuente == 'calendario':
                    fecha_partido_iso = (datetime.combine(pc.fecha, pc.hora or time(18, 0)).isoformat()if pc.fecha else None)
                else:  
                    fecha_partido_iso = (pc.fecha_partido.isoformat() if pc.fecha_partido else None)

                clas_rival = (
                    ClasificacionJornada.objects.filter(equipo=rival, temporada=temporada,jornada__numero_jornada__lte=jornada_actual)
                    .order_by('-jornada__numero_jornada')
                    .first()
                )

                racha_rival_detalles = []
                goles_rival_favor = 0
                goles_rival_contra = 0
                if clas_rival:
                    goles_rival_favor = clas_rival.goles_favor
                    goles_rival_contra = clas_rival.goles_contra
                    racha_rival_detalles = get_racha_detalles(rival, temporada, clas_rival.jornada)

                max_goleador_equipo = (
                    get_maximo_goleador(equipo, temporada, jornada_actual_obj)
                    if jornada_actual_obj
                    else None
                )
                max_goleador_rival = (
                    get_maximo_goleador(rival, temporada, jornada_actual_obj)
                    if jornada_actual_obj
                    else None
                )
                partido_anterior = (
                    get_partido_anterior_temporada(equipo, rival, temporada, jornada_actual_obj)
                    if jornada_actual_obj
                    else None
                )

                proximo_partido = {
                    'equipo_local': pc.equipo_local.nombre,
                    'equipo_visitante': pc.equipo_visitante.nombre,
                    'fecha_partido': fecha_partido_iso,
                }

                rival_info = {
                    'nombre': rival.nombre,
                    'escudo': shield_name(rival.nombre),
                    'es_local': es_local,
                    'racha': racha_rival_detalles,
                    'goles_favor': goles_rival_favor,
                    'goles_contra': goles_rival_contra,
                    'h2h': get_h2h_historico(equipo, rival, temporada),
                    'max_goleador_equipo': max_goleador_equipo,
                    'max_goleador_rival': max_goleador_rival,
                    'partido_anterior': partido_anterior,
                }

        historico_temporadas = get_historico_temporadas(equipo)

        try:
            ultimas_3_stats = get_estadisticas_equipo_temporadas(equipo, num_temporadas=3)
            ultimas_3_jugadores = get_jugadores_ultimas_temporadas(equipo, num_temporadas=3)
        except Exception:
            ultimas_3_stats = {
                'temporadas': [],
                'total_goles': 0,
                'total_asistencias': 0,
                'partidos_jugados': 0,
            }
            ultimas_3_jugadores = []

        suggested_temporada = None
        if not jugadores:
            for t in temporadas:  
                if EquipoJugadorTemporada.objects.filter(equipo=equipo, temporada=t).exists():
                    suggested_temporada = t.nombre
                    break

        return Response({
            'equipo': {
                'id': equipo.id,
                'nombre': equipo.nombre,
                'escudo': shield_name(equipo.nombre),
                'estadio': equipo.estadio or '',
            },
            'jugadores': jugadores,
            'clasificacion': {
                'posicion': clasificacion_actual.posicion,
                'puntos': clasificacion_actual.puntos,
            } if clasificacion_actual else {},
            'racha_actual_detalles': racha_actual_detalles,
            'temporadas_display': temporadas_display,
            'temporada_actual': temporada_display,
            'temporada_actual_db': temporada.nombre if temporada else None,
            'jornadas_disponibles': jornadas_disponibles,
            'jornada_actual': jornada_actual,
            'jornada_min': jornada_min,
            'jornada_max': jornada_max,
            'proximo_partido': proximo_partido,
            'rival_info': rival_info,
            'top_3_puntos': top_3_puntos,
            'top_3_minutos': top_3_minutos,
            'ultimas_3_jugadores': ultimas_3_jugadores,
            'ultimas_3_stats': ultimas_3_stats,
            'historico_temporadas': historico_temporadas,
            'goles_equipo_favor': goles_equipo_favor,
            'goles_equipo_contra': goles_equipo_contra,
            'suggested_temporada': suggested_temporada,
        })
