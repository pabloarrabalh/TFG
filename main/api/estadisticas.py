"""
DRF API – Estadísticas Completas de Jugadores
Endpoints:
  GET /api/estadisticas/
  GET /api/estadisticas/comparacion/
"""
import logging
from statistics import mode, StatisticsError

from django.db.models import Sum, Avg, Count, Q, Case, When, IntegerField, F
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import AllowAny

from ..models import *
from ..views.utils import shield_name
from ..cache_utils import cache_api_response

logger = logging.getLogger(__name__)


def calcular_puntos_fantasy_filtrados_lista(puntos_lista):
    """
    Calcula puntos_fantasy filtrando outliers > 40 y reemplazándolos con la moda.
    
    Args:
        puntos_lista: Lista de valores puntos_fantasy
    
    Returns:
        int: Suma de puntos con outliers reemplazados por la moda
    """
    if not puntos_lista:
        return 0
    
    # Filtrar puntos válidos (≤ 40)
    puntos_validos = [p for p in puntos_lista if p and p <= 40]
    
    if not puntos_validos:
        # Si todos son > 40, retornar 0 para no contar outliers
        return 0
    
    # Calcular la moda de los puntos válidos
    try:
        moda = mode(puntos_validos)
    except StatisticsError:
        # Si hay múltiples modas o sin datos, usar la media
        moda = sum(puntos_validos) // len(puntos_validos) if puntos_validos else 0
    
    # Reemplazar outliers (> 40) con la moda
    puntos_finales = []
    for p in puntos_lista:
        if p and p > 40:
            puntos_finales.append(moda)
        elif p:
            puntos_finales.append(p)
    
    return sum(puntos_finales) if puntos_finales else 0


class EstadisticasView(APIView):
    """GET /api/estadisticas/?temporada=25_26&jornada=6&tipo=goles"""
    permission_classes = [AllowAny]

    @cache_api_response(timeout=120, key_prefix='estadisticas')
    def get(self, request):
        temporada_str = request.query_params.get('temporada', '25_26')
        jornada_num = request.query_params.get('jornada')
        jornada_desde = request.query_params.get('jornada_desde')
        jornada_hasta = request.query_params.get('jornada_hasta')
        tipo = request.query_params.get('tipo')  # Sin default - None si no se envía
        search = request.query_params.get('search', '')
        limit = int(request.query_params.get('limit', 50))
        offset = int(request.query_params.get('offset', 0))

        try:
            temporada = Temporada.objects.get(nombre=temporada_str)
        except Temporada.DoesNotExist:
            return Response({'estadisticas': [], 'total': 0})

        # Base query
        stats_qs = EstadisticasPartidoJugador.objects.filter(
            partido__jornada__temporada=temporada
        ).select_related('jugador', 'partido__equipo_local', 'partido__equipo_visitante')

        # Filtrar por jornada específica o rango de jornadas
        if jornada_num:
            try:
                jornada = Jornada.objects.get(numero_jornada=int(jornada_num), temporada=temporada)
                stats_qs = stats_qs.filter(partido__jornada=jornada)
            except (ValueError, Jornada.DoesNotExist):
                pass
        else:
            # Filtrar por rango de jornadas
            if jornada_desde:
                try:
                    jornada_desde_num = int(jornada_desde)
                    stats_qs = stats_qs.filter(partido__jornada__numero_jornada__gte=jornada_desde_num)
                except (ValueError, TypeError):
                    pass
            
            if jornada_hasta:
                try:
                    jornada_hasta_num = int(jornada_hasta)
                    stats_qs = stats_qs.filter(partido__jornada__numero_jornada__lte=jornada_hasta_num)
                except (ValueError, TypeError):
                    pass

        # Filtrar por búsqueda
        if search:
            search_lower = search.lower()
            stats_qs = stats_qs.filter(
                Q(jugador__nombre__icontains=search_lower) |
                Q(jugador__apellido__icontains=search_lower)
            )

        # Agrupar por jugador
        jugador_stats = stats_qs.values('jugador_id', 'jugador__nombre', 'jugador__apellido').annotate(
            total_goles=Sum('gol_partido'),
            total_asistencias=Sum('asist_partido'),
            total_amarillas=Sum('amarillas'),
            total_rojas=Sum('rojas'),
            total_xg=Sum('xg_partido'),
            total_xag=Sum('xag'),
            total_despejes=Sum('despejes'),
            total_entradas=Sum('entradas'),
            total_duelos=Sum('duelos'),
            total_duelos_ganados=Sum('duelos_ganados'),
            total_duelos_perdidos=Sum('duelos_perdidos'),
            total_duelos_aereos_ganados=Sum('duelos_aereos_ganados'),
            total_duelos_aereos_perdidos=Sum('duelos_aereos_perdidos'),
            total_tiros=Sum('tiros'),
            total_regates=Sum('regates_completados'),
            total_goles_en_contra=Sum('goles_en_contra'),
            avg_porcentaje_paradas=Avg('porcentaje_paradas'),
            partidos_jugados=Count('id'),
            minutos_totales=Sum('min_partido'),
        ).order_by('-total_goles')

        # Leer corners/penaltis/faltas desde roles JSON (los campos de partido suelen ser 0)
        # Formato roles: [{"corners": [pos, valor]}, ...]
        _ROLES_CAMPOS = ('corners', 'penaltis_marcados', 'faltas_recibidas')
        roles_qs = (
            EstadisticasPartidoJugador.objects
            .filter(partido__jornada__temporada=temporada)
            .exclude(roles__isnull=True)
            .exclude(roles__exact=[])
            .values('jugador_id', 'roles')
        )
        roles_por_jugador = {}
        for r in roles_qs:
            jid = r['jugador_id']
            roles_list = r['roles']
            if not roles_list or not isinstance(roles_list, list):
                continue
            if jid not in roles_por_jugador:
                roles_por_jugador[jid] = {}
            for role_obj in roles_list:
                if isinstance(role_obj, dict):
                    for fn, values in role_obj.items():
                        if fn in _ROLES_CAMPOS and isinstance(values, list) and len(values) >= 2:
                            pos, val = values[0], values[1]
                            # Guardar la mejor posición (menor pos = mejor ranking)
                            if fn not in roles_por_jugador[jid] or pos < roles_por_jugador[jid][fn][0]:
                                roles_por_jugador[jid][fn] = (pos, val)

        # Pre-calcular puntos_fantasy filtrados (sin outliers > 40)
        puntos_por_jugador = {}
        for jugador_id in [stat['jugador_id'] for stat in jugador_stats]:
            puntos_lista = list(stats_qs.filter(jugador_id=jugador_id).values_list('puntos_fantasy', flat=True))
            puntos_por_jugador[jugador_id] = calcular_puntos_fantasy_filtrados_lista(puntos_lista)

        # Pre-fetch todos los EquipoJugadorTemporada en una sola query (elimina N+1)
        ejt_bulk = EquipoJugadorTemporada.objects.filter(
            temporada=temporada
        ).select_related('equipo').values(
            'jugador_id', 'equipo__nombre', 'posicion'
        )
        ejt_map = {e['jugador_id']: e for e in ejt_bulk}

        # Agregar equipo e información adicional
        resultado = []
        for stat in jugador_stats:
            try:
                ejt_data = ejt_map.get(stat['jugador_id'])
                ejt = type('EJT', (), {
                    'equipo': type('Equipo', (), {'nombre': ejt_data['equipo__nombre']})() if ejt_data else None,
                    'posicion': ejt_data['posicion'] if ejt_data else 'Desconocida'
                })()
                if not ejt_data:
                    ejt = None

                tarjetas_total = (stat['total_amarillas'] or 0) + (stat['total_rojas'] or 0)
                row = {
                    'jugador_id': stat['jugador_id'],
                    'nombre': stat['jugador__nombre'],
                    'apellido': stat['jugador__apellido'],
                    'equipo': ejt.equipo.nombre if ejt else '—',
                    'equipo_escudo': shield_name(ejt.equipo.nombre) if ejt else None,
                    'posicion': ejt.posicion if ejt else 'Desconocida',
                    'goles': stat['total_goles'] or 0,
                    'asistencias': stat['total_asistencias'] or 0,
                    'amarillas': stat['total_amarillas'] or 0,
                    'rojas': stat['total_rojas'] or 0,
                    'tarjetas': tarjetas_total,
                    'xg': round(stat['total_xg'] or 0, 2),
                    'xag': round(stat['total_xag'] or 0, 2),
                    'goles_vs_xg': (stat['total_goles'] or 0) - (stat['total_xg'] or 0),
                    'asistencias_vs_xag': (stat['total_asistencias'] or 0) - (stat['total_xag'] or 0),
                    'despejes': stat['total_despejes'] or 0,
                    'entradas': stat['total_entradas'] or 0,
                    'duelos_totales': stat['total_duelos'] or 0,
                    'duelos_ganados': stat['total_duelos_ganados'] or 0,
                    'duelos_perdidos': stat['total_duelos_perdidos'] or 0,
                    'duelos_aereos_ganados': stat['total_duelos_aereos_ganados'] or 0,
                    'duelos_aereos_perdidos': stat['total_duelos_aereos_perdidos'] or 0,
                    'tiros': stat['total_tiros'] or 0,
                    'regates_completados': stat['total_regates'] or 0,
                    'puntos_fantasy': puntos_por_jugador.get(stat['jugador_id'], 0),
                    'goles_en_contra': stat['total_goles_en_contra'] or 0,
                    'porcentaje_paradas': round(stat['avg_porcentaje_paradas'] or 0.0, 1),
                    'corners': int(roles_por_jugador.get(stat['jugador_id'], {}).get('corners', (0, 0))[1]),
                    'penaltis_marcados': int(roles_por_jugador.get(stat['jugador_id'], {}).get('penaltis_marcados', (0, 0))[1]),
                    'faltas_recibidas': int(roles_por_jugador.get(stat['jugador_id'], {}).get('faltas_recibidas', (0, 0))[1]),
                    'partidos': stat['partidos_jugados'],
                    'minutos': stat['minutos_totales'] or 0,
                }
                resultado.append(row)
            except Exception as exc:
                logger.warning(f'Error procesando jugador {stat["jugador_id"]}: {exc}')
                continue

        # Ordenar según tipo
        if tipo:
            # Si hay un tipo seleccionado, ordenar por ese
            if tipo == 'goles':
                resultado.sort(key=lambda x: x['goles'], reverse=True)
            elif tipo == 'asistencias':
                resultado.sort(key=lambda x: x['asistencias'], reverse=True)
            elif tipo == 'amarillas':
                resultado.sort(key=lambda x: x['amarillas'], reverse=True)
            elif tipo == 'rojas':
                resultado.sort(key=lambda x: x['rojas'], reverse=True)
            elif tipo == 'puntos_fantasy':
                resultado.sort(key=lambda x: x['puntos_fantasy'], reverse=True)
            elif tipo == 'xg_diff':
                resultado.sort(key=lambda x: x['goles_vs_xg'], reverse=True)
            elif tipo == 'xag_diff':
                resultado.sort(key=lambda x: x['asistencias_vs_xag'], reverse=True)
            elif tipo == 'corners':
                resultado.sort(key=lambda x: x['corners'], reverse=True)
            elif tipo == 'penaltis_marcados':
                resultado.sort(key=lambda x: x['penaltis_marcados'], reverse=True)
            elif tipo == 'faltas_recibidas':
                resultado.sort(key=lambda x: x['faltas_recibidas'], reverse=True)
        else:
            # Si no hay tipo, ordenar alfabéticamente por nombre
            resultado.sort(key=lambda x: (x['nombre'] or '').lower() + ' ' + (x['apellido'] or '').lower())

        # Calcular percentiles POR POSICIÓN para múltiples stats
        if resultado:
            # Agrupar por posición
            jugadores_por_posicion = {}
            for row in resultado:
                pos = row['posicion'].strip().upper()
                if pos not in jugadores_por_posicion:
                    jugadores_por_posicion[pos] = []
                jugadores_por_posicion[pos].append(row)
            
            # Stats a calcular percentiles (diferentes para cada posición)
            stats_generales = ['goles', 'asistencias', 'tarjetas', 'minutos', 'tiros', 'regates_completados', 'puntos_fantasy', 'xg', 'xag', 'goles_vs_xg', 'asistencias_vs_xag', 'corners', 'penaltis_marcados', 'faltas_recibidas']
            stats_defensa = ['despejes', 'entradas', 'duelos_ganados', 'duelos_aereos_ganados']
            stats_portero = ['minutos', 'goles_en_contra', 'porcentaje_paradas', 'despejes']  # Porteros: minutos, golesEC, parada%, despejes
            
            # Calcular percentiles dentro de cada posición
            for pos, jugadores_pos in jugadores_por_posicion.items():
                is_portero = 'PORTERO' in pos or pos == 'PT'
                
                # Seleccionar estadísticas según posición
                if is_portero:
                    stats_to_calc = stats_generales + stats_portero
                elif 'DEFENSA' in pos or pos == 'DF':
                    stats_to_calc = stats_generales + stats_defensa
                else:
                    stats_to_calc = stats_generales + ['despejes', 'entradas']
                
                # Calcular percentil para cada stat
                for stat_key in stats_to_calc:
                    values = [r.get(stat_key, 0) for r in jugadores_pos]
                    
                    if values and len(values) > 1:
                        # Verificar si todos los valores son iguales
                        unique_values = set(values)
                        if len(unique_values) == 1:
                            # Todos tienen el mismo valor - todos comparten el mismo percentil
                            percentil = 50  # Neutral: todos están en la mitad
                            for row in jugadores_pos:
                                row[f'{stat_key}_percentil'] = percentil
                        else:
                            # Hay variación - calcular percentilespropiamente
                            for row in jugadores_pos:
                                val = row.get(stat_key, 0)
                                # Contar cuántos jugadores tienen MENOS que este
                                count_lower = sum(1 for v in values if v < val)
                                # Percentil con manejo de empates: usar posición media entre iguales
                                count_equal = sum(1 for v in values if v == val)
                                percentil = int(((count_lower + count_equal * 0.5) / (len(values) - 1 if len(values) > 1 else 1)) * 100)
                                row[f'{stat_key}_percentil'] = max(0, min(100, percentil))
                    else:
                        # Sin datos suficientes
                        for row in jugadores_pos:
                            row[f'{stat_key}_percentil'] = 0

        return Response({
            'estadisticas': resultado[offset:offset+limit],
            'total_count': len(resultado),
            'tipo': tipo,
        })


class ComparacionJugadoresView(APIView):
    """GET /api/estadisticas/comparacion/?jugador_ids=1,2,3&temporada=25_26"""
    permission_classes = [AllowAny]

    def get(self, request):
        jugador_ids = request.query_params.get('jugador_ids', '').split(',')
        jugador_ids = [int(id) for id in jugador_ids if id.isdigit()]
        
        temporada_str = request.query_params.get('temporada', '25_26')
        
        if not jugador_ids:
            return Response({'jugadores': []})

        try:
            temporada = Temporada.objects.get(nombre=temporada_str)
        except Temporada.DoesNotExist:
            return Response({'jugadores': []})

        resultado = []
        for jugador_id in jugador_ids:
            try:
                jugador = Jugador.objects.get(id=jugador_id)
                stats_qs = EstadisticasPartidoJugador.objects.filter(
                    jugador=jugador,
                    partido__jornada__temporada=temporada
                )
                
                # Calcular puntos_fantasy filtrados
                puntos_lista = list(stats_qs.values_list('puntos_fantasy', flat=True))
                puntos_fantasy_filtrado = calcular_puntos_fantasy_filtrados_lista(puntos_lista)
                
                stats = stats_qs.aggregate(
                    goles=Sum('gol_partido'),
                    asistencias=Sum('asist_partido'),
                    amarillas=Sum('amarillas'),
                    rojas=Sum('rojas'),
                    xg=Sum('xg_partido'),
                    xag=Sum('xag'),
                    despejes=Sum('despejes'),
                    entradas=Sum('entradas'),
                    duelos_totales=Sum('duelos'),
                    duelos_ganados=Sum('duelos_ganados'),
                    duelos_perdidos=Sum('duelos_perdidos'),
                    duelos_aereos_ganados=Sum('duelos_aereos_ganados'),
                    duelos_aereos_perdidos=Sum('duelos_aereos_perdidos'),
                    tiros=Sum('tiros'),
                    regates_completados=Sum('regates_completados'),
                    minutos=Sum('min_partido'),
                    partidos=Count('id'),
                )

                ejt = EquipoJugadorTemporada.objects.filter(
                    jugador=jugador,
                    temporada=temporada
                ).first()

                resultado.append({
                    'jugador_id': jugador.id,
                    'nombre': jugador.nombre,
                    'apellido': jugador.apellido,
                    'equipo': ejt.equipo.nombre if ejt else '—',
                    'equipo_escudo': shield_name(ejt.equipo.nombre) if ejt else None,
                    'posicion': ejt.posicion if ejt else 'Desconocida',
                    'goles': stats['goles'] or 0,
                    'asistencias': stats['asistencias'] or 0,
                    'amarillas': stats['amarillas'] or 0,
                    'rojas': stats['rojas'] or 0,
                    'xg': round(stats['xg'] or 0, 2),
                    'xag': round(stats['xag'] or 0, 2),
                    'despejes': stats['despejes'] or 0,
                    'entradas': stats['entradas'] or 0,
                    'duelos_totales': stats['duelos_totales'] or 0,
                    'duelos_ganados': stats['duelos_ganados'] or 0,
                    'duelos_perdidos': stats['duelos_perdidos'] or 0,
                    'duelos_aereos_ganados': stats['duelos_aereos_ganados'] or 0,
                    'duelos_aereos_perdidos': stats['duelos_aereos_perdidos'] or 0,
                    'tiros': stats['tiros'] or 0,
                    'regates_completados': stats['regates_completados'] or 0,
                    'puntos_fantasy': puntos_fantasy_filtrado,
                    'minutos': stats['minutos'] or 0,
                    'partidos': stats['partidos'],
                    'goles_promedio': round((stats['goles'] or 0) / (stats['partidos'] or 1), 2),
                    'asistencias_promedio': round((stats['asistencias'] or 0) / (stats['partidos'] or 1), 2),
                })
            except Jugador.DoesNotExist:
                continue

        return Response({'jugadores': resultado})
