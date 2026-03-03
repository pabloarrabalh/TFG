"""Jugador (player) view"""
from django.shortcuts import render
from django.db.models import Sum, Count, Q, Avg

from .models import (
    Temporada, Jornada, Jugador, EquipoJugadorTemporada, EstadisticasPartidoJugador,
)
from .views_utils import calcular_percentil
from main.scrapping.roles import DESCRIPCIONES_ROLES


def jugador(request, jugador_id=None, temporada=None):
    """Vista de estadísticas de jugador"""
    if not jugador_id:
        return render(request, 'jugador.html', {'active_page': 'estadisticas', 'error': 'Jugador no encontrado'})

    try:
        jugador_obj = Jugador.objects.get(id=jugador_id)
    except Jugador.DoesNotExist:
        return render(request, 'jugador.html', {'active_page': 'estadisticas', 'error': 'Jugador no encontrado'})

    temporadas_jugador = EquipoJugadorTemporada.objects.filter(
        jugador=jugador_obj
    ).values_list('temporada__nombre', flat=True).distinct().order_by('-temporada__nombre')

    es_carrera = temporada == 'carrera'

    if not temporada and temporadas_jugador:
        temporada_obj = Temporada.objects.get(nombre=temporadas_jugador[0])
    elif temporada and not es_carrera:
        try:
            temporada_obj = Temporada.objects.get(nombre=temporada)
        except Temporada.DoesNotExist:
            temporada_obj = Temporada.objects.get(nombre=temporadas_jugador[0]) if temporadas_jugador else None
    elif es_carrera:
        temporada_obj = Temporada.objects.get(nombre=temporadas_jugador[0]) if temporadas_jugador else None
    else:
        temporada_obj = None

    if not temporada_obj:
        return render(request, 'jugador.html', {'active_page': 'estadisticas', 'error': 'Temporada no encontrada'})

    if es_carrera:
        equipo_temporada = EquipoJugadorTemporada.objects.filter(jugador=jugador_obj).first()
    else:
        equipo_temporada = EquipoJugadorTemporada.objects.filter(
            jugador=jugador_obj, temporada=temporada_obj
        ).first()

    if not equipo_temporada:
        return render(request, 'jugador.html', {
            'active_page': 'estadisticas',
            'jugador': jugador_obj,
            'temporada_obj': temporada_obj,
            'temporadas_disponibles': [{'nombre': t, 'display': t.replace('_', '/')} for t in temporadas_jugador],
            'error': 'Jugador no jugó en esta temporada',
        })

    filter_query = Q(jugador=jugador_obj) if es_carrera else Q(jugador=jugador_obj, partido__jornada__temporada=temporada_obj)

    stats = EstadisticasPartidoJugador.objects.filter(filter_query).exclude(puntos_fantasy__gt=40).aggregate(
        total_goles=Sum('gol_partido'),
        total_asistencias=Sum('asist_partido'),
        total_minutos=Sum('min_partido'),
        total_partidos=Count('id', filter=Q(min_partido__gt=0)),
        promedio_puntos=Avg('puntos_fantasy'),
        total_pases=Sum('pases_totales'),
        pases_accuracy=Avg('pases_completados_pct'),
        total_xag=Sum('xag'),
        total_regates=Sum('regates'),
        regates_completados=Sum('regates_completados'),
        regates_fallidos=Sum('regates_fallidos'),
        conducciones_progresivas=Sum('conducciones_progresivas'),
        total_conducciones=Sum('conducciones'),
        distancia_conduccion=Sum('distancia_conduccion'),
        metros_avanzados_conduccion=Sum('metros_avanzados_conduccion'),
        total_despejes=Sum('despejes'),
        total_entradas=Sum('entradas'),
        duelos_ganados=Sum('duelos_ganados'),
        duelos_perdidos=Sum('duelos_perdidos'),
        duelos=Sum('duelos'),
        total_amarillas=Sum('amarillas'),
        total_rojas=Sum('rojas'),
        bloqueo_pase=Sum('bloqueo_pase'),
        bloqueo_tiros=Sum('bloqueo_tiros'),
        total_bloqueos=Sum('bloqueos'),
        duelos_aereos_ganados=Sum('duelos_aereos_ganados'),
        duelos_aereos_perdidos=Sum('duelos_aereos_perdidos'),
        duelos_aereos_pct=Avg('duelos_aereos_ganados_pct'),
        total_tiros=Sum('tiros'),
        tiros_puerta=Sum('tiro_puerta_partido'),
        tiros_fallados=Sum('tiro_fallado_partido'),
        total_xg=Sum('xg_partido'),
        goles_en_contra=Sum('goles_en_contra'),
        porcentaje_paradas=Avg('porcentaje_paradas'),
        psxg=Sum('psxg'),
    )

    if es_carrera:
        ultimos_12 = (
            EstadisticasPartidoJugador.objects.filter(jugador=jugador_obj)
            .exclude(puntos_fantasy__gt=40)
            .select_related('partido', 'partido__jornada')
            .order_by('-partido__jornada__temporada', '-partido__jornada__numero_jornada')[:12]
        )
    else:
        ultimos_12 = (
            EstadisticasPartidoJugador.objects.filter(jugador=jugador_obj, partido__jornada__temporada=temporada_obj)
            .exclude(puntos_fantasy__gt=40)
            .select_related('partido', 'partido__jornada')
            .order_by('-partido__jornada__numero_jornada')[:12]
        )

    ultimos_12_ordenados = list(reversed(ultimos_12))

    if es_carrera:
        stats_con_roles = (
            EstadisticasPartidoJugador.objects.filter(jugador=jugador_obj, roles__isnull=False)
            .exclude(puntos_fantasy__gt=40).exclude(roles__exact=[])
            .values_list('roles', flat=True)
        )
    else:
        stats_con_roles = (
            EstadisticasPartidoJugador.objects.filter(
                jugador=jugador_obj,
                partido__jornada__temporada=temporada_obj,
                roles__isnull=False,
            )
            .exclude(puntos_fantasy__gt=40).exclude(roles__exact=[])
            .values_list('roles', flat=True)
        )

    roles_dict = {}
    for stats_roles in stats_con_roles:
        if stats_roles and isinstance(stats_roles, list):
            for role_obj in stats_roles:
                if isinstance(role_obj, dict):
                    for field_name, values in role_obj.items():
                        if field_name not in roles_dict or values[0] < roles_dict[field_name][0]:
                            roles_dict[field_name] = values

    roles = [roles_dict] if roles_dict else []

    historico = EquipoJugadorTemporada.objects.filter(
        jugador=jugador_obj
    ).select_related('equipo', 'temporada').order_by('-temporada')

    historico_data = []
    for hist in historico:
        stats_hist = EstadisticasPartidoJugador.objects.filter(
            jugador=jugador_obj,
            partido__jornada__temporada=hist.temporada,
        ).exclude(puntos_fantasy__gt=40).aggregate(
            goles=Sum('gol_partido'),
            asistencias=Sum('asist_partido'),
            minutos=Sum('min_partido'),
            partidos=Count('id', filter=Q(min_partido__gt=0)),
            promedio_puntos=Avg('puntos_fantasy'),
            puntos_totales=Sum('puntos_fantasy'),
            pases=Sum('pases_totales'),
            pases_accuracy=Avg('pases_completados_pct'),
            xag=Sum('xag'),
            despejes=Sum('despejes'),
            entradas=Sum('entradas'),
            duelos_ganados=Sum('duelos_ganados'),
            duelos_perdidos=Sum('duelos_perdidos'),
            amarillas=Sum('amarillas'),
            rojas=Sum('rojas'),
            bloqueos=Sum('bloqueos'),
            bloqueo_tiros=Sum('bloqueo_tiros'),
            bloqueo_pase=Sum('bloqueo_pase'),
            duelos_aereos_ganados=Sum('duelos_aereos_ganados'),
            duelos_aereos_perdidos=Sum('duelos_aereos_perdidos'),
            tiros=Sum('tiros'),
            tiros_puerta=Sum('tiro_puerta_partido'),
            xg=Sum('xg_partido'),
            regates_completados=Sum('regates_completados'),
            regates_fallidos=Sum('regates_fallidos'),
            conducciones=Sum('conducciones'),
            conducciones_progresivas=Sum('conducciones_progresivas'),
            distancia_conduccion=Sum('distancia_conduccion'),
        )
        partidos_count = stats_hist['partidos'] or 0
        puntos_totales = stats_hist['puntos_totales'] or 0
        puntos_por_partido = round(puntos_totales / partidos_count, 1) if partidos_count > 0 else 0

        historico_data.append({
            'temporada': hist.temporada.nombre.replace('_', '/'),
            'temporada_numero': hist.temporada.nombre,
            'equipo': hist.equipo.nombre,
            'dorsal': hist.dorsal or '-',
            'puntos_totales': puntos_totales,
            'puntos_por_partido': puntos_por_partido,
            'goles': stats_hist['goles'] or 0,
            'asistencias': stats_hist['asistencias'] or 0,
            'pj': partidos_count,
            'minutos': stats_hist['minutos'] or 0,
            'promedio_puntos': round(stats_hist['promedio_puntos'] or 0, 1),
            'pases': stats_hist['pases'] or 0,
            'pases_accuracy': round(stats_hist['pases_accuracy'] or 0, 1),
            'xag': round(stats_hist['xag'] or 0, 2),
            'despejes': stats_hist['despejes'] or 0,
            'entradas': stats_hist['entradas'] or 0,
            'duelos_ganados': stats_hist['duelos_ganados'] or 0,
            'duelos_perdidos': stats_hist['duelos_perdidos'] or 0,
            'duelos_totales': (stats_hist['duelos_ganados'] or 0) + (stats_hist['duelos_perdidos'] or 0),
            'amarillas': stats_hist['amarillas'] or 0,
            'rojas': stats_hist['rojas'] or 0,
            'bloqueos': stats_hist['bloqueos'] or 0,
            'bloqueo_tiros': stats_hist['bloqueo_tiros'] or 0,
            'bloqueo_pase': stats_hist['bloqueo_pase'] or 0,
            'duelos_aereos_ganados': stats_hist['duelos_aereos_ganados'] or 0,
            'duelos_aereos_perdidos': stats_hist['duelos_aereos_perdidos'] or 0,
            'duelos_aereos_totales': (stats_hist['duelos_aereos_ganados'] or 0) + (stats_hist['duelos_aereos_perdidos'] or 0),
            'tiros': stats_hist['tiros'] or 0,
            'tiros_puerta': stats_hist['tiros_puerta'] or 0,
            'xg': round(stats_hist['xg'] or 0, 2),
            'regates_completados': stats_hist['regates_completados'] or 0,
            'regates_fallidos': stats_hist['regates_fallidos'] or 0,
            'conducciones': stats_hist['conducciones'] or 0,
            'conducciones_progresivas': stats_hist['conducciones_progresivas'] or 0,
            'distancia_conduccion': round(stats_hist['distancia_conduccion'] or 0, 1),
        })

    posicion = jugador_obj.get_posicion_mas_frecuente()
    percentiles = equipo_temporada.percentiles if equipo_temporada.percentiles else {}

    posicion_map = {
        'Portero': 'PT', 'Defensa': 'DF', 'Centrocampista': 'MC', 'Delantero': 'DT',
    }
    posicion_color_map = {
        'Portero': '59, 130, 246',
        'Defensa': '34, 197, 94',
        'Centrocampista': '234, 179, 8',
        'Delantero': '239, 68, 68',
    }

    context = {
        'active_page': 'estadisticas',
        'jugador': jugador_obj,
        'equipo_temporada': equipo_temporada,
        'temporada_obj': temporada_obj,
        'temporada_display': 'Carrera' if es_carrera else temporada_obj.nombre.replace('_', '/'),
        'es_carrera': es_carrera,
        'temporadas_disponibles': [{'nombre': t, 'display': t.replace('_', '/')} for t in temporadas_jugador],
        'stats': {
            'goles': stats['total_goles'] or 0,
            'asistencias': stats['total_asistencias'] or 0,
            'minutos': stats['total_minutos'] or 0,
            'partidos': stats['total_partidos'] or 0,
            'promedio_puntos': round(stats['promedio_puntos'] or 0, 1),
            'organizacion': {
                'pases': stats['total_pases'] or 0,
                'pases_accuracy': round(stats['pases_accuracy'] or 0, 1),
                'xag': round(stats['total_xag'] or 0, 2),
            },
            'regates_block': {
                'regates_completados': stats['regates_completados'] or 0,
                'regates_fallidos': stats['regates_fallidos'] or 0,
                'conducciones_progresivas': stats['conducciones_progresivas'] or 0,
                'conducciones': stats['total_conducciones'] or 0,
                'distancia_conduccion': round(stats['distancia_conduccion'] or 0, 1),
                'metros_avanzados': round(stats['metros_avanzados_conduccion'] or 0, 1),
            },
            'defensa': {
                'despejes': stats['total_despejes'] or 0,
                'entradas': stats['total_entradas'] or 0,
                'duelos_ganados': stats['duelos_ganados'] or 0,
                'duelos_perdidos': stats['duelos_perdidos'] or 0,
                'duelos': (stats['duelos_ganados'] or 0) + (stats['duelos_perdidos'] or 0),
                'amarillas': stats['total_amarillas'] or 0,
                'rojas': stats['total_rojas'] or 0,
                'bloqueo_pase': stats['bloqueo_pase'] or 0,
                'bloqueo_tiros': stats['bloqueo_tiros'] or 0,
                'bloqueos': stats['total_bloqueos'] or 0,
                'duelos_aereos_ganados': stats['duelos_aereos_ganados'] or 0,
                'duelos_aereos_perdidos': stats['duelos_aereos_perdidos'] or 0,
                'duelos_aereos_pct': round(stats['duelos_aereos_pct'] or 0, 1),
            },
            'ataque': {
                'goles': stats['total_goles'] or 0,
                'tiros_puerta': stats['tiros_puerta'] or 0,
                'tiros_fallados': stats['tiros_fallados'] or 0,
                'tiros': stats['total_tiros'] or 0,
                'xg': round(stats['total_xg'] or 0, 2),
            },
            'portero': {
                'goles_en_contra': stats['goles_en_contra'] or 0,
                'porcentaje_paradas': round(stats['porcentaje_paradas'] or 0, 1),
                'pases': stats['total_pases'] or 0,
                'psxg': round(stats['psxg'] or 0, 2),
            },
        },
        'ultimos_8': ultimos_12_ordenados,
        'historico': historico_data,
        'posicion': posicion,
        'posicion_corta': posicion_map.get(posicion, 'N/A'),
        'posicion_color': posicion_color_map.get(posicion, '156, 163, 175'),
        'edad': equipo_temporada.edad or 0,
        'roles': roles,
        'descripciones_roles': DESCRIPCIONES_ROLES,
        'percentiles': percentiles,
        'radar_values': [],
        'media_general': 0,
    }

    return render(request, 'jugador.html', context)
