"""Equipo (team) views"""
from datetime import datetime, time

from django.shortcuts import render
from django.db.models import Sum, Count, Q

from .models import (
    Temporada, Jornada, Equipo, EquipoJugadorTemporada,
    EstadisticasPartidoJugador, ClasificacionJornada, Calendario,
)
from .views_utils import (
    get_informacion_equipo,
    get_racha_detalles,
    get_racha_futura,
    get_historico_temporadas,
    get_maximo_goleador,
    get_partido_anterior_temporada,
    get_h2h_historico,
    get_estadisticas_equipo_temporadas,
    get_jugadores_ultimas_temporadas,
    normalize_team_name_python,
    similitud_nombres,
)
from .models import EquipoFavorito


def equipos(request):
    """Vista de lista de equipos con información agregada"""
    equipos_list = Equipo.objects.all().order_by('nombre')

    favoritos_ids = set()
    if request.user.is_authenticated:
        favoritos_ids = set(
            EquipoFavorito.objects.filter(usuario=request.user).values_list('equipo_id', flat=True)
        )

    equipos_info = [
        {'equipo': eq, 'info': get_informacion_equipo(eq), 'es_favorito': eq.id in favoritos_ids}
        for eq in equipos_list
    ]

    context = {
        'active_page': 'equipos',
        'equipos_info': equipos_info,
        'favoritos_ids': favoritos_ids,
    }

    return render(request, 'equipos.html', context)


def equipo(request, equipo_nombre=None, temporada=None):
    """Vista de detalles de equipo con plantilla de jugadores que jugaron"""
    temporada_display = request.GET.get('temporada') or temporada or '25/26'
    temporada_nombre = temporada_display.replace('/', '_')

    temporadas = Temporada.objects.all().order_by('-nombre')
    temporadas_display = [
        {'nombre': t.nombre, 'display': t.nombre.replace('_', '/')}
        for t in temporadas
    ]

    equipo_obj = None
    jugadores = []
    equipo_display_nombre = equipo_nombre or 'FC Barcelona'
    jornadas_disponibles = []
    jornada_actual = None
    jornada_min = 1
    jornada_max = 38
    racha_actual = []
    proximo_partido = None
    rival_info = None
    goles_equipo_favor = 0
    goles_equipo_contra = 0
    racha_actual_detalles = []
    racha_futura_detalles = []
    historico_temporadas = []
    ultimas_3_stats = None
    ultimas_3_jugadores = None
    top_3_puntos = []
    top_3_minutos = []
    jornada_actual_obj = None

    try:
        equipo_obj = Equipo.objects.get(nombre=equipo_display_nombre)

        try:
            temp_obj = Temporada.objects.get(nombre=temporada_nombre)
        except Temporada.DoesNotExist:
            temp_obj = temporadas.first()
            temporada_nombre = temp_obj.nombre if temp_obj else '24_25'
            temporada_display = temporada_nombre.replace('_', '/')

        jornadas_temp = Jornada.objects.filter(temporada=temp_obj).order_by('numero_jornada')
        jornadas_disponibles = [{'numero': j.numero_jornada} for j in jornadas_temp]

        ultima_jornada_clasificacion = (
            Jornada.objects.filter(temporada=temp_obj, clasificacionjornada__isnull=False)
            .order_by('numero_jornada').last()
        )
        ultima_jornada_clasificacion = ultima_jornada_clasificacion.numero_jornada if ultima_jornada_clasificacion else 1

        jornada_num = request.GET.get('jornada')
        if jornada_num:
            try:
                jornada_actual = int(jornada_num)
                if not jornadas_temp.filter(numero_jornada=jornada_actual).exists():
                    jornada_actual = None
            except (ValueError, TypeError):
                jornada_actual = None

        if jornada_actual is None:
            jornada_actual = ultima_jornada_clasificacion

        jugadores_equipo_temp = EquipoJugadorTemporada.objects.filter(
            equipo=equipo_obj,
            temporada=temp_obj,
        ).select_related('jugador').order_by('dorsal')

        jugadores_agrupados = {}
        puntos_dorsal_cero = {}

        for eq_jug_temp in jugadores_equipo_temp:
            stats_query = EstadisticasPartidoJugador.objects.filter(
                jugador=eq_jug_temp.jugador,
                partido__jornada__temporada=temp_obj,
            )
            if jornada_actual:
                stats_query = stats_query.filter(partido__jornada__numero_jornada__lte=jornada_actual)

            valid_stats = stats_query.exclude(puntos_fantasy__gt=40)
            total_puntos = valid_stats.aggregate(Sum('puntos_fantasy'))['puntos_fantasy__sum'] or 0
            partidos_jugados = valid_stats.count()
            total_minutos = valid_stats.aggregate(Sum('min_partido'))['min_partido__sum'] or 0

            if eq_jug_temp.dorsal == 0 and total_puntos <= 0:
                nombre_completo = f"{eq_jug_temp.jugador.nombre} {eq_jug_temp.jugador.apellido}".strip()
                puntos_dorsal_cero[nombre_completo] = {
                    'puntos': total_puntos,
                    'nombre': eq_jug_temp.jugador.nombre,
                    'apellido': eq_jug_temp.jugador.apellido,
                }
                continue

            posicion_frecuente = stats_query.values('posicion').annotate(
                count=Count('id')
            ).order_by('-count').first()

            jugador_id = eq_jug_temp.jugador.id
            if jugador_id not in jugadores_agrupados:
                jugadores_agrupados[jugador_id] = {
                    'obj': eq_jug_temp,
                    'total_puntos': total_puntos,
                    'partidos_stats': partidos_jugados,
                    'total_minutos': total_minutos,
                    'posicion': posicion_frecuente['posicion'] if posicion_frecuente else None,
                    'nombre': eq_jug_temp.jugador.nombre,
                    'apellido': eq_jug_temp.jugador.apellido,
                }
            else:
                jugadores_agrupados[jugador_id]['total_puntos'] += total_puntos

        # Match dorsal-0 negative points to main player records
        for nombre_dorsal_cero, datos_dorsal_cero in puntos_dorsal_cero.items():
            mejor_coincidencia = None
            mejor_similitud = 0.6

            for jugador_id, datos_principal in jugadores_agrupados.items():
                nombre_principal = f"{datos_principal['nombre']} {datos_principal['apellido']}".strip()
                sim = similitud_nombres(nombre_dorsal_cero, nombre_principal)
                if sim > mejor_similitud:
                    mejor_similitud = sim
                    mejor_coincidencia = jugador_id

            if mejor_coincidencia:
                jugadores_agrupados[mejor_coincidencia]['total_puntos'] += datos_dorsal_cero['puntos']

        for jugador_id, datos in jugadores_agrupados.items():
            eq_jug_temp_obj = datos['obj']
            total_puntos = datos['total_puntos']
            partidos_jugados = datos['partidos_stats']
            total_minutos = datos['total_minutos']

            promedio_puntos = total_puntos / partidos_jugados if partidos_jugados > 0 else 0

            eq_jug_temp_obj.total_puntos_fantasy = total_puntos
            eq_jug_temp_obj.partidos_stats = partidos_jugados
            eq_jug_temp_obj.total_minutos = total_minutos
            eq_jug_temp_obj.promedio_puntos_fantasy = round(promedio_puntos, 2)
            eq_jug_temp_obj.posicion = datos['posicion']

            jugadores.append(eq_jug_temp_obj)

        top_3_puntos = sorted(jugadores, key=lambda x: x.total_puntos_fantasy, reverse=True)[:3]
        top_3_minutos = sorted(jugadores, key=lambda x: x.total_minutos, reverse=True)[:3]

        clasificacion_actual = ClasificacionJornada.objects.filter(
            equipo=equipo_obj,
            temporada=temp_obj,
            jornada__numero_jornada__lte=jornada_actual if jornada_actual else jornada_max,
        ).order_by('-jornada__numero_jornada').first()

        if clasificacion_actual:
            goles_equipo_favor = clasificacion_actual.goles_favor
            goles_equipo_contra = clasificacion_actual.goles_contra
            if clasificacion_actual.racha_reciente:
                racha_map = {'W': 'V', 'D': 'E', 'L': 'P'}
                racha_actual = [racha_map.get(r, r) for r in list(clasificacion_actual.racha_reciente)]

        if jornada_actual:
            try:
                jornada_actual_obj = Jornada.objects.get(temporada=temp_obj, numero_jornada=jornada_actual)
            except Jornada.DoesNotExist:
                jornada_actual_obj = None

        if jornada_actual and jornada_actual < jornada_max:
            proximo_encontrado = None
            for offset in range(1, (jornada_max - jornada_actual) + 1):
                partidos_intentar = Calendario.objects.filter(
                    jornada__temporada=temp_obj,
                    jornada__numero_jornada=jornada_actual + offset,
                ).filter(
                    Q(equipo_local=equipo_obj) | Q(equipo_visitante=equipo_obj)
                ).first()
                if partidos_intentar:
                    proximo_encontrado = partidos_intentar
                    break

            if proximo_encontrado:
                partido_calendario = proximo_encontrado

                if partido_calendario.equipo_local == equipo_obj:
                    rival = partido_calendario.equipo_visitante
                    es_local = True
                    estadio_partido = equipo_obj.estadio or 'Estadio desconocido'
                else:
                    rival = partido_calendario.equipo_local
                    es_local = False
                    estadio_partido = rival.estadio or 'Estadio desconocido'

                class PartidoInfo:
                    pass

                proximo_partido = PartidoInfo()
                proximo_partido.equipo_local = partido_calendario.equipo_local
                proximo_partido.equipo_visitante = partido_calendario.equipo_visitante
                proximo_partido.fecha_partido = datetime.combine(
                    partido_calendario.fecha, partido_calendario.hora or time(18, 0)
                )
                proximo_partido.goles_local = None
                proximo_partido.goles_visitante = None

                clasificacion_rival = ClasificacionJornada.objects.filter(
                    equipo=rival,
                    temporada=temp_obj,
                    jornada__numero_jornada__lte=jornada_actual,
                ).order_by('-jornada__numero_jornada').first()

                if clasificacion_rival:
                    goles_rival_favor = clasificacion_rival.goles_favor
                    goles_rival_contra = clasificacion_rival.goles_contra

                    jornada_rival_obj = clasificacion_rival.jornada
                    racha_rival_detalles = get_racha_detalles(rival, temp_obj, jornada_rival_obj)

                    max_goleador_equipo = get_maximo_goleador(equipo_obj, temp_obj, jornada_actual_obj) if jornada_actual_obj else None
                    max_goleador_rival = get_maximo_goleador(rival, temp_obj, jornada_actual_obj) if jornada_actual_obj else None
                    partido_anterior = get_partido_anterior_temporada(equipo_obj, rival, temp_obj, jornada_actual_obj) if jornada_actual_obj else None

                    rival_info = {
                        'nombre': rival.nombre,
                        'iniciales': ''.join([p[0].upper() for p in rival.nombre.split()]),
                        'nombre_normalizado': normalize_team_name_python(rival.nombre),
                        'es_local': es_local,
                        'estadio_rival': rival.estadio or 'Estadio desconocido',
                        'estadio_partido': estadio_partido,
                        'racha': racha_rival_detalles,
                        'goles_favor': goles_rival_favor,
                        'goles_contra': goles_rival_contra,
                        'h2h': get_h2h_historico(equipo_obj, rival, temp_obj),
                        'max_goleador_equipo': max_goleador_equipo,
                        'max_goleador_rival': max_goleador_rival,
                        'partido_anterior': partido_anterior,
                    }

    except Equipo.DoesNotExist:
        pass

    iniciales = ''
    if equipo_obj:
        iniciales = ''.join([p[0].upper() for p in equipo_obj.nombre.split()])

        if jornada_actual_obj:
            racha_actual_detalles = get_racha_detalles(equipo_obj, temp_obj, jornada_actual_obj)
            racha_futura_detalles = get_racha_futura(equipo_obj, temp_obj, jornada_actual_obj)

        historico_temporadas = get_historico_temporadas(equipo_obj)
        ultimas_3_stats = get_estadisticas_equipo_temporadas(equipo_obj, num_temporadas=3)
        ultimas_3_jugadores = get_jugadores_ultimas_temporadas(equipo_obj, num_temporadas=3)

    context = {
        'active_page': 'equipos',
        'equipo': equipo_obj,
        'equipo_nombre': equipo_display_nombre,
        'iniciales': iniciales,
        'jugadores': jugadores,
        'top_3_puntos': top_3_puntos,
        'top_3_minutos': top_3_minutos,
        'temporadas_display': temporadas_display,
        'temporada_actual': temporada_nombre,
        'temporada_actual_url': temporada_nombre,
        'temporada_actual_db': temporada_nombre,
        'jornadas_disponibles': jornadas_disponibles,
        'jornada_actual': jornada_actual,
        'jornada_min': jornada_min,
        'jornada_max': jornada_max,
        'proximo_partido': proximo_partido,
        'rival_info': rival_info,
        'goles_equipo_favor': goles_equipo_favor,
        'goles_equipo_contra': goles_equipo_contra,
        'racha_actual': racha_actual,
        'racha_actual_detalles': racha_actual_detalles,
        'racha_futura_detalles': racha_futura_detalles,
        'historico_temporadas': historico_temporadas,
        'ultimas_3_stats': ultimas_3_stats,
        'ultimas_3_jugadores': ultimas_3_jugadores,
        'desde_clasificacion': equipo_nombre is not None,
    }

    return render(request, 'equipo.html', context)
