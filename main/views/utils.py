"""
Shared helper utilities used by all views_*.py modules.
No Django request/response logic here — pure data helpers.
"""
import unicodedata
import re
from difflib import SequenceMatcher

from django.db.models import Sum, Q, Count, Avg
from django.core.cache import cache

from ..models import (
    Temporada, Jornada, Partido, Calendario,
    ClasificacionJornada, EstadisticasPartidoJugador,
    EquipoJugadorTemporada,
)


# ── Name helpers ──────────────────────────────────────────────────────────────

def normalize_team_name_python(nombre):
    """Normaliza el nombre del equipo para usar en clases CSS (replica del filtro template)"""
    if not nombre:
        return ''

    normalized = nombre.lower().strip()

    prefixes = ['fc ', 'cd ', 'ad ', 'rcd ', 'real ', 'ud ', 'cf ', 'sd ', 'ef ', 'ca ']
    for prefix in prefixes:
        if normalized.startswith(prefix):
            normalized = normalized[len(prefix):]
            break

    normalized = ''.join(
        c for c in unicodedata.normalize('NFD', normalized)
        if unicodedata.category(c) != 'Mn'
    )
    normalized = normalized.replace(' ', '-')
    normalized = ''.join(c if c.isalnum() or c == '-' else '' for c in normalized)
    return normalized


def shield_name(nombre):
    """Replicates the Django template filter for shield image filenames."""
    if not nombre:
        return ''
    n = nombre.lower().strip()

    n = ''.join(c for c in unicodedata.normalize('NFD', n) if unicodedata.category(c) != 'Mn')

    special_cases = {
        'atletico': 'atletico',
        'athletic': 'athletic_club',
        'rayo': 'rayo_vallecano',
        'celta': 'celta',
    }
    for key, replacement in special_cases.items():
        if n.startswith(key):
            return replacement

    for p in ['fc ', 'cd ', 'ad ', 'rcd ', 'real ', 'ud ', 'cf ', 'sd ', 'ef ', 'ca ']:
        if n.startswith(p):
            n = n[len(p):]
            break

    n = n.replace(' ', '_')
    n = re.sub(r'[^a-z0-9_]', '', n)
    return n


def similitud_nombres(nombre1, nombre2):
    """Calcula similitud entre dos nombres (0-1)"""
    return SequenceMatcher(None, nombre1.lower(), nombre2.lower()).ratio()


# ── Match/streak helpers ──────────────────────────────────────────────────────

def get_racha_detalles(equipo, temporada, jornada_actual):
    """Obtiene los detalles de los últimos 5 partidos jugados incluyendo la jornada actual si se ha jugado"""
    partidos = Partido.objects.filter(
        jornada__temporada=temporada,
        jornada__numero_jornada__lte=jornada_actual.numero_jornada,
        goles_local__isnull=False,
        goles_visitante__isnull=False,
    ).filter(
        Q(equipo_local=equipo) | Q(equipo_visitante=equipo)
    ).select_related('equipo_local', 'equipo_visitante', 'jornada').order_by(
        '-jornada__numero_jornada', '-fecha_partido'
    )[:5]

    racha_detalles = []

    for partido in partidos:
        es_local = partido.equipo_local == equipo
        if es_local:
            rival = partido.equipo_visitante.nombre
            goles_propios = partido.goles_local
            goles_rival = partido.goles_visitante
        else:
            rival = partido.equipo_local.nombre
            goles_propios = partido.goles_visitante
            goles_rival = partido.goles_local

        if goles_propios > goles_rival:
            resultado = 'V'
            titulo = f"Victoria vs {rival} {goles_propios}-{goles_rival}"
        elif goles_propios < goles_rival:
            resultado = 'D'
            titulo = f"Derrota vs {rival} {goles_propios}-{goles_rival}"
        else:
            resultado = 'E'
            titulo = f"Empate vs {rival} {goles_propios}-{goles_rival}"

        racha_detalles.append({
            'resultado': resultado,
            'titulo': titulo,
            'rival': rival,
            'goles_propios': goles_propios,
            'goles_rival': goles_rival,
        })

    # Si la jornada actual no tiene resultado aún, añadir marcador de partido pendiente
    partido_actual_sin_resultado = Calendario.objects.filter(
        jornada=jornada_actual
    ).filter(
        Q(equipo_local=equipo) | Q(equipo_visitante=equipo)
    ).first()

    if partido_actual_sin_resultado and len(racha_detalles) < 5:
        partido_con_resultado = Partido.objects.filter(
            jornada=jornada_actual,
            equipo_local=partido_actual_sin_resultado.equipo_local,
            equipo_visitante=partido_actual_sin_resultado.equipo_visitante,
            goles_local__isnull=False,
            goles_visitante__isnull=False,
        ).exists()

        if not partido_con_resultado:
            racha_detalles.append({
                'resultado': '?',
                'titulo': 'Partido por jugar',
                'rival': '',
                'goles_propios': None,
                'goles_rival': None,
            })

    racha_detalles.reverse()
    return racha_detalles


def get_racha_futura(equipo, temporada, jornada_actual):
    """Obtiene los próximos 5 partidos sin resultado (futuros) incluyendo jornada actual si no se ha jugado"""
    partidos = Calendario.objects.filter(
        jornada__temporada=temporada,
        jornada__numero_jornada__gte=jornada_actual.numero_jornada,
    ).filter(
        Q(equipo_local=equipo) | Q(equipo_visitante=equipo)
    ).select_related('equipo_local', 'equipo_visitante', 'jornada').order_by(
        'jornada__numero_jornada', 'fecha', 'hora'
    )[:5]

    racha_futura = []

    for partido_cal in partidos:
        es_local = partido_cal.equipo_local == equipo
        rival = partido_cal.equipo_visitante.nombre if es_local else partido_cal.equipo_local.nombre

        partido_con_resultado = Partido.objects.filter(
            jornada=partido_cal.jornada,
            equipo_local=partido_cal.equipo_local,
            equipo_visitante=partido_cal.equipo_visitante,
            goles_local__isnull=False,
            goles_visitante__isnull=False,
        ).first()

        if partido_con_resultado:
            goles_propios = partido_con_resultado.goles_local if es_local else partido_con_resultado.goles_visitante
            goles_rival = partido_con_resultado.goles_visitante if es_local else partido_con_resultado.goles_local

            if goles_propios > goles_rival:
                resultado = 'V'
            elif goles_propios < goles_rival:
                resultado = 'L'
            else:
                resultado = 'D'

            titulo = f"Jornada {partido_cal.jornada.numero_jornada} vs {rival} {goles_propios}-{goles_rival}"
        else:
            resultado = '?'
            goles_propios = None
            goles_rival = None
            titulo = f"Jornada {partido_cal.jornada.numero_jornada} - vs {rival}"

        racha_futura.append({
            'resultado': resultado,
            'titulo': titulo,
            'rival': rival,
            'goles_propios': goles_propios,
            'goles_rival': goles_rival,
            'jornada': partido_cal.jornada.numero_jornada,
        })

    return racha_futura


def get_historico_temporadas(equipo):
    """Obtiene las estadísticas de cada temporada (V/E/P, GF, GC, DF, Posición)"""
    temporadas = Temporada.objects.all().order_by('-nombre')
    historico = []

    for temporada in temporadas:
        ultima_jornada = Jornada.objects.filter(temporada=temporada).order_by('-numero_jornada').first()

        if ultima_jornada:
            partidos = Partido.objects.filter(
                jornada__temporada=temporada,
                goles_local__isnull=False,
                goles_visitante__isnull=False,
            ).filter(Q(equipo_local=equipo) | Q(equipo_visitante=equipo))

            victorias = derrotas = empates = goles_favor = goles_contra = 0

            for partido in partidos:
                es_local = partido.equipo_local == equipo
                goles_propios = partido.goles_local if es_local else partido.goles_visitante
                goles_rival = partido.goles_visitante if es_local else partido.goles_local

                goles_favor += goles_propios
                goles_contra += goles_rival

                if goles_propios > goles_rival:
                    victorias += 1
                elif goles_propios < goles_rival:
                    derrotas += 1
                else:
                    empates += 1

            clasificacion = ClasificacionJornada.objects.filter(
                equipo=equipo,
                jornada__temporada=temporada,
            ).order_by('-jornada__numero_jornada').first()

            if clasificacion or (victorias + derrotas + empates > 0):
                historico.append({
                    'temporada': temporada.nombre.replace('_', '/'),
                    'posicion': clasificacion.posicion if clasificacion else 21,
                    'victorias': victorias,
                    'empates': empates,
                    'derrotas': derrotas,
                    'goles_favor': goles_favor,
                    'goles_contra': goles_contra,
                    'diferencia_goles': goles_favor - goles_contra,
                })

    return historico


def get_maximo_goleador(equipo, temporada, jornada_actual):
    """Obtiene el máximo goleador de un equipo hasta una jornada específica en una temporada"""
    estadisticas = EstadisticasPartidoJugador.objects.filter(
        partido__jornada__temporada=temporada,
        partido__jornada__numero_jornada__lte=jornada_actual.numero_jornada,
        partido__goles_local__isnull=False,
    ).filter(
        Q(partido__equipo_local=equipo) | Q(partido__equipo_visitante=equipo)
    ).values('jugador', 'jugador__nombre', 'jugador__apellido').annotate(
        total_goles=Sum('gol_partido')
    ).order_by('-total_goles').first()

    if estadisticas:
        return {
            'nombre': estadisticas['jugador__nombre'],
            'apellido': estadisticas['jugador__apellido'],
            'goles': estadisticas['total_goles'],
        }
    return None


def get_partido_anterior_temporada(equipo1, equipo2, temporada, jornada_actual):
    """Busca si ya se jugó un partido entre dos equipos en la temporada actual (antes de la jornada actual)"""
    partido = Partido.objects.filter(
        jornada__temporada=temporada,
        jornada__numero_jornada__lt=jornada_actual.numero_jornada,
        goles_local__isnull=False,
    ).filter(
        Q(Q(equipo_local=equipo1) & Q(equipo_visitante=equipo2))
        | Q(Q(equipo_local=equipo2) & Q(equipo_visitante=equipo1))
    ).first()

    if partido:
        es_local = partido.equipo_local == equipo1
        goles_eq1 = partido.goles_local if es_local else partido.goles_visitante
        goles_eq2 = partido.goles_visitante if es_local else partido.goles_local
        return {
            'jornada': partido.jornada.numero_jornada,
            'goles_equipo1': goles_eq1,
            'goles_equipo2': goles_eq2,
            'es_local': es_local,
            'resultado': 'V' if goles_eq1 > goles_eq2 else ('E' if goles_eq1 == goles_eq2 else 'P'),
        }
    return None


def get_h2h_historico(equipo1, equipo2, temporada=None):
    """Obtiene el histórico H2H entre dos equipos.
    Si se especifica temporada, incluye esa y todas las anteriores (no futuro).
    """
    partidos_filter = Partido.objects.filter(
        goles_local__isnull=False,
        goles_visitante__isnull=False,
    ).filter(
        Q(Q(equipo_local=equipo1) & Q(equipo_visitante=equipo2))
        | Q(Q(equipo_local=equipo2) & Q(equipo_visitante=equipo1))
    )

    if temporada:
        partidos_filter = partidos_filter.filter(
            jornada__temporada__nombre__lte=temporada.nombre
        )

    partidos = partidos_filter.select_related(
        'equipo_local', 'equipo_visitante', 'jornada__temporada'
    ).order_by('-jornada__temporada__nombre', '-jornada__numero_jornada')

    victorias_eq1 = derrotas_eq1 = empates_eq1 = 0
    ultimos_5 = []

    for partido in partidos:
        es_local = partido.equipo_local == equipo1
        goles_propios = partido.goles_local if es_local else partido.goles_visitante
        goles_rival = partido.goles_visitante if es_local else partido.goles_local
        rival = partido.equipo_visitante if es_local else partido.equipo_local

        if goles_propios > goles_rival:
            victorias_eq1 += 1
            resultado = 'V'
        elif goles_propios < goles_rival:
            derrotas_eq1 += 1
            resultado = 'P'
        else:
            empates_eq1 += 1
            resultado = 'E'

        if len(ultimos_5) < 5:
            ultimos_5.append({
                'resultado': resultado,
                'contra': rival.nombre,
                'goles_propios': goles_propios,
                'goles_rival': goles_rival,
                'temporada': partido.jornada.temporada.nombre.replace('_', '/'),
            })

    return {
        'victorias': victorias_eq1,
        'derrotas': derrotas_eq1,
        'empates': empates_eq1,
        'total': victorias_eq1 + derrotas_eq1 + empates_eq1,
        'ultimos_5': ultimos_5,
    }


# ── Team aggregate stats ──────────────────────────────────────────────────────

def get_estadisticas_equipo_temporadas(equipo, num_temporadas=3):
    """Obtiene estadísticas agregadas de un equipo para las últimas N temporadas"""
    temporadas = Temporada.objects.all().order_by('-nombre')[:num_temporadas]

    eq_jug_temp = EquipoJugadorTemporada.objects.filter(
        equipo=equipo,
        temporada__in=temporadas,
    ).values_list('jugador_id', flat=True)

    stats = EstadisticasPartidoJugador.objects.filter(
        Q(partido__equipo_local=equipo) | Q(partido__equipo_visitante=equipo),
        jugador_id__in=eq_jug_temp,
        partido__jornada__temporada__in=temporadas,
        partido__goles_local__isnull=False,
    )

    partidos_jugados = stats.filter(min_partido__gt=0).values('partido').distinct().count()

    return {
        'temporadas': [t.nombre.replace('_', '/') for t in temporadas],
        'total_goles': stats.aggregate(Sum('gol_partido'))['gol_partido__sum'] or 0,
        'total_asistencias': stats.aggregate(Sum('asist_partido'))['asist_partido__sum'] or 0,
        'partidos_jugados': partidos_jugados,
    }


def get_jugadores_ultimas_temporadas(equipo, num_temporadas=3):
    """Obtiene jugadores y sus estadísticas agregadas para las últimas N temporadas."""
    temporadas = Temporada.objects.all().order_by('-nombre')[:num_temporadas]

    ejt_qs = (
        EquipoJugadorTemporada.objects
        .filter(equipo=equipo, temporada__in=temporadas)
        .select_related('jugador', 'temporada')
        .order_by('temporada__nombre')
    )

    posicion_map = {}
    nac_map = {}
    dorsal_map = {}
    for ejt in ejt_qs:
        jid = ejt.jugador_id
        posicion_map[jid] = ejt.posicion or ''
        nac_map[jid] = ejt.jugador.nacionalidad or ''
        dorsal_map[jid] = ejt.dorsal

    jugadores_ids = list(posicion_map.keys())

    jugadores_stats = EstadisticasPartidoJugador.objects.filter(
        Q(partido__equipo_local=equipo) | Q(partido__equipo_visitante=equipo),
        jugador_id__in=jugadores_ids,
        partido__jornada__temporada__in=temporadas,
        partido__goles_local__isnull=False,
    ).values(
        'jugador', 'jugador__nombre', 'jugador__apellido',
    ).annotate(
        total_goles=Sum('gol_partido'),
        total_asistencias=Sum('asist_partido'),
        total_minutos=Sum('min_partido'),
        total_puntos_fantasy=Sum('puntos_fantasy'),
        partidos_count=Count('id'),
    ).order_by('-total_goles', '-total_asistencias')

    result = []
    for js in jugadores_stats:
        jid = js['jugador']
        result.append({
            **js,
            'posicion': posicion_map.get(jid, ''),
            'jugador__nacionalidad': nac_map.get(jid, ''),
            'dorsal': dorsal_map.get(jid),
            'total_puntos_fantasy': js.get('total_puntos_fantasy') or 0,
        })
    return result


def get_informacion_equipo(equipo):
    """Obtiene información completa de un equipo: máximo goleador, asistente, máximos partidos jugados"""
    jugadores_ids = EquipoJugadorTemporada.objects.filter(
        equipo=equipo
    ).values_list('jugador_id', flat=True).distinct()

    base_filter = EstadisticasPartidoJugador.objects.filter(
        Q(partido__equipo_local=equipo) | Q(partido__equipo_visitante=equipo),
        jugador_id__in=jugadores_ids,
        partido__goles_local__isnull=False,
    )

    max_goleador = base_filter.values(
        'jugador', 'jugador__nombre', 'jugador__apellido'
    ).annotate(total_goles=Sum('gol_partido')).order_by('-total_goles').first()

    max_asistente = base_filter.values(
        'jugador', 'jugador__nombre', 'jugador__apellido'
    ).annotate(total_asistencias=Sum('asist_partido')).order_by('-total_asistencias').first()

    max_partidos = base_filter.filter(min_partido__gt=0).values(
        'jugador', 'jugador__nombre', 'jugador__apellido'
    ).annotate(total_partidos=Count('id')).order_by('-total_partidos').first()

    return {
        'max_goleador': {
            'nombre': max_goleador['jugador__nombre'],
            'apellido': max_goleador['jugador__apellido'],
            'goles': max_goleador['total_goles'],
        } if max_goleador else None,
        'max_asistente': {
            'nombre': max_asistente['jugador__nombre'],
            'apellido': max_asistente['jugador__apellido'],
            'asistencias': max_asistente['total_asistencias'],
        } if max_asistente else None,
        'max_partidos': {
            'nombre': max_partidos['jugador__nombre'],
            'apellido': max_partidos['jugador__apellido'],
            'partidos': max_partidos['total_partidos'],
        } if max_partidos else None,
    }


# ── Percentile helper ─────────────────────────────────────────────────────────

def calcular_percentil(jugador_obj, temporada_obj, posicion, stat_field, es_carrera=False):
    """
    Calcula el percentil de un jugador para un stat específico dentro de su posición y temporada.
    Retorna un número entre 0 y 100. Usa caché para evitar recálculos.
    """
    from scipy import stats as scipy_stats

    temp_name = temporada_obj.nombre if temporada_obj else 'all'
    cache_key = f"percentil_{jugador_obj.id}_{temp_name}_{posicion}_{stat_field}"

    cached_value = cache.get(cache_key)
    if cached_value is not None:
        return cached_value

    try:
        if es_carrera:
            misma_posicion = EstadisticasPartidoJugador.objects.filter(
                posicion=posicion
            ).values('jugador').distinct()
        else:
            misma_posicion = EstadisticasPartidoJugador.objects.filter(
                posicion=posicion,
                partido__jornada__temporada=temporada_obj,
            ).values('jugador').distinct()

        jugadores_posicion = [jug['jugador'] for jug in misma_posicion]

        if not jugadores_posicion:
            return 50

        valores = []
        for jug_id in jugadores_posicion:
            if es_carrera:
                query = EstadisticasPartidoJugador.objects.filter(jugador_id=jug_id)
            else:
                query = EstadisticasPartidoJugador.objects.filter(
                    jugador_id=jug_id,
                    partido__jornada__temporada=temporada_obj,
                )
            agg = query.aggregate(stat_value=Sum(stat_field))
            valores.append(float(agg['stat_value'] or 0))

        if not valores:
            return 50

        if es_carrera:
            jugador_value = EstadisticasPartidoJugador.objects.filter(
                jugador=jugador_obj
            ).aggregate(suma=Sum(stat_field))['suma'] or 0
        else:
            jugador_value = EstadisticasPartidoJugador.objects.filter(
                jugador=jugador_obj,
                partido__jornada__temporada=temporada_obj,
            ).aggregate(suma=Sum(stat_field))['suma'] or 0

        percentil = int(scipy_stats.percentileofscore(valores, float(jugador_value)))
        cache.set(cache_key, percentil, 3600)
        return percentil

    except Exception:
        return 50
