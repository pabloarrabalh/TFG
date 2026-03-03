"""ML prediction API endpoint views"""
import json
import sys
import logging
import traceback
from pathlib import Path

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.db.models import Avg
from django.conf import settings

from .models import Jugador, PrediccionJugador, Jornada, Temporada, Calendario, Partido, EquipoJugadorTemporada, EstadisticasPartidoJugador

logger = logging.getLogger(__name__)

_ENTRENAMIENTOS_PATH = Path(__file__).parent / 'entrenamientoModelos'


def _ensure_path():
    if str(_ENTRENAMIENTOS_PATH) not in sys.path:
        sys.path.insert(0, str(_ENTRENAMIENTOS_PATH))


@csrf_exempt
def predecir_portero_api(request):
    """
    POST /api/predecir_portero/
    Body: {jugador_id, jornada?, modelo?}
    Returns: {status, prediccion, jornada, modelo, ...}
    """
    try:
        data = json.loads(request.body.decode('utf-8') if isinstance(request.body, bytes) else request.body)
        jugador_id = data.get('jugador_id')
        jornada = data.get('jornada', None)
        modelo_tipo = data.get('modelo', 'RF')

        if not jugador_id:
            return JsonResponse({'status': 'error', 'error': 'jugador_id es requerido'}, status=400)

        try:
            jugador = Jugador.objects.get(id=jugador_id)
        except Jugador.DoesNotExist:
            return JsonResponse({'status': 'error', 'error': f'Jugador con ID {jugador_id} no encontrado'}, status=404)

        nombre_jugador = f"{jugador.nombre} {jugador.apellido}".strip()
        _ensure_path()
        from predecir import predecir_puntos_portero

        resultado = predecir_puntos_portero(nombre_jugador, jornada, verbose=False, modelo_tipo=modelo_tipo)

        if not isinstance(resultado, dict):
            return JsonResponse({'status': 'error', 'error': f'Resultado inválido: {resultado}'}, status=500)

        if resultado.get('error'):
            return JsonResponse({'status': 'error', 'error': resultado['error'], 'jugador_id': jugador_id}, status=400)

        prediccion = resultado.get('prediccion')
        return JsonResponse({
            'status': 'success',
            'jugador_id': jugador_id,
            'jugador_nombre': nombre_jugador,
            'prediccion': float(prediccion) if prediccion is not None else None,
            'puntos_reales': float(resultado['puntos_reales']) if resultado['puntos_reales'] is not None else None,
            'puntos_reales_texto': resultado.get('puntos_reales_texto', 'Aún no jugado'),
            'margen': float(resultado.get('margen', 0)),
            'rango_min': float(resultado.get('rango_min')) if resultado.get('rango_min') is not None else None,
            'rango_max': float(resultado.get('rango_max')) if resultado.get('rango_max') is not None else None,
            'jornada': int(resultado['jornada']),
            'modelo': resultado.get('modelo', 'Random Forest'),
        })

    except json.JSONDecodeError as e:
        return JsonResponse({'status': 'error', 'error': f'JSON inválido: {e}'}, status=400)
    except ImportError as e:
        logger.error(f"[API] Error importando módulo: {e}", exc_info=True)
        return JsonResponse({'status': 'error', 'error': f'Error de módulo: {e}'}, status=500)
    except Exception as e:
        logger.error(f"[API] Error inesperado: {e}", exc_info=True)
        return JsonResponse({
            'status': 'error',
            'error': str(e),
            'traceback': traceback.format_exc() if settings.DEBUG else None,
        }, status=500)


@csrf_exempt
def cambiar_jornada_api(request):
    """
    POST /api/cambiar_jornada/
    Body: {jornada: int}
    Returns jugadores_por_posicion updated for that jornada.
    """
    try:
        data = json.loads(request.body.decode('utf-8') if isinstance(request.body, bytes) else request.body)
        nueva_jornada = data.get('jornada')

        if not nueva_jornada or not isinstance(nueva_jornada, int):
            return JsonResponse({'status': 'error', 'error': 'jornada debe ser un entero'}, status=400)

        temporada_actual = Temporada.objects.last()
        if not temporada_actual:
            return JsonResponse({'status': 'error', 'error': 'No hay temporada disponible'}, status=404)

        jornada_actual = Jornada.objects.filter(
            temporada=temporada_actual, numero_jornada=nueva_jornada
        ).first()
        if not jornada_actual:
            return JsonResponse({'status': 'error', 'error': f'Jornada {nueva_jornada} no existe'}, status=404)

        partidos_por_jornada = {}
        for partido in Partido.objects.filter(jornada=jornada_actual).select_related('equipo_local', 'equipo_visitante'):
            partidos_por_jornada[partido.equipo_local.id] = {
                'rival_id': partido.equipo_visitante.id,
                'rival_nombre': partido.equipo_visitante.nombre,
                'es_local': True,
            }
            partidos_por_jornada[partido.equipo_visitante.id] = {
                'rival_id': partido.equipo_local.id,
                'rival_nombre': partido.equipo_local.nombre,
                'es_local': False,
            }

        if not partidos_por_jornada:
            for cal in Calendario.objects.filter(jornada=jornada_actual).select_related('equipo_local', 'equipo_visitante'):
                partidos_por_jornada[cal.equipo_local.id] = {
                    'rival_id': cal.equipo_visitante.id, 'rival_nombre': cal.equipo_visitante.nombre, 'es_local': True,
                }
                partidos_por_jornada[cal.equipo_visitante.id] = {
                    'rival_id': cal.equipo_local.id, 'rival_nombre': cal.equipo_local.nombre, 'es_local': False,
                }

        jugadores_por_posicion = {'Portero': [], 'Defensa': [], 'Centrocampista': [], 'Delantero': []}

        for ejt in EquipoJugadorTemporada.objects.filter(
            temporada=temporada_actual
        ).select_related('jugador', 'equipo').order_by('jugador__nombre'):
            posicion = ejt.posicion or 'Delantero'
            jugador = ejt.jugador

            stats_puntos = EstadisticasPartidoJugador.objects.filter(
                partido__jornada__temporada=temporada_actual,
                jugador=jugador,
                puntos_fantasy__lte=50,
            ).aggregate(total_puntos=Sum('puntos_fantasy'))

            rival_jornada = partidos_por_jornada.get(ejt.equipo.id)

            if posicion in jugadores_por_posicion:
                jugadores_por_posicion[posicion].append({
                    'id': jugador.id,
                    'nombre': jugador.nombre,
                    'apellido': jugador.apellido,
                    'posicion': posicion,
                    'equipo_id': ejt.equipo.id,
                    'equipo_nombre': ejt.equipo.nombre,
                    'puntos_fantasy_25_26': stats_puntos['total_puntos'] or 0,
                    'proximo_rival_id': rival_jornada['rival_id'] if rival_jornada else None,
                    'proximo_rival_nombre': rival_jornada['rival_nombre'] if rival_jornada else None,
                })

        return JsonResponse({
            'status': 'success',
            'jornada': nueva_jornada,
            'jugadores_por_posicion': jugadores_por_posicion,
        })

    except Exception as e:
        logger.error(f"[API] Error en cambiar_jornada: {e}\n{traceback.format_exc()}")
        return JsonResponse({'status': 'error', 'error': str(e)}, status=500)


@csrf_exempt
def explicar_prediccion_portero_api(request):
    """
    POST /api/explicar_prediccion/
    Body: {jugador_id, jornada?, posicion?, modelo?}
    Returns prediction + SHAP explainability features.
    """
    try:
        data = json.loads(request.body.decode('utf-8') if isinstance(request.body, bytes) else request.body)
        jugador_id = data.get('jugador_id')
        jornada = data.get('jornada', None)
        posicion_raw = data.get('posicion', None)
        modelo_tipo = data.get('modelo', None)

        if not jugador_id:
            return JsonResponse({'status': 'error', 'error': 'jugador_id es requerido'}, status=400)

        try:
            jugador = Jugador.objects.get(id=jugador_id)
            nombre_jugador = f"{jugador.nombre} {jugador.apellido}".strip()
        except Jugador.DoesNotExist:
            return JsonResponse({'status': 'error', 'error': f'Jugador {jugador_id} no encontrado'}, status=404)

        MAP_POS = {
            'portero': 'PT', 'pt': 'PT', 'gk': 'PT',
            'defensa': 'DF', 'df': 'DF', 'defensor': 'DF',
            'centrocampista': 'MC', 'mediocampista': 'MC', 'mc': 'MC', 'mf': 'MC',
            'delantero': 'DT', 'dt': 'DT', 'fw': 'DT', 'st': 'DT',
        }
        if posicion_raw:
            posicion_code = MAP_POS.get(str(posicion_raw).lower(), str(posicion_raw).upper())
        else:
            pos_bd = getattr(jugador, 'posicion', None) or ''
            posicion_code = MAP_POS.get(str(pos_bd).lower(), 'DT')

        _ensure_path()
        from predecir import predecir_puntos

        resultado = predecir_puntos(jugador_id, posicion_code, jornada, verbose=False, modelo_tipo=modelo_tipo)

        if resultado.get('error'):
            return JsonResponse({'status': 'error', 'error': resultado['error'], 'jugador_id': jugador_id}, status=400)

        prediccion = resultado.get('prediccion')
        return JsonResponse({
            'status': 'success',
            'jugador_id': jugador_id,
            'jugador_nombre': nombre_jugador,
            'posicion': posicion_code,
            'prediccion': float(prediccion) if prediccion is not None else None,
            'puntos_reales': float(resultado['puntos_reales']) if resultado.get('puntos_reales') is not None else None,
            'puntos_reales_texto': resultado.get('puntos_reales_texto', 'Aún no jugado'),
            'jornada': int(resultado.get('jornada', jornada or 0)),
            'modelo': resultado.get('modelo', ''),
            'features_impacto': resultado.get('features_impacto', []),
            'explicacion_texto': resultado.get('explicacion_texto', ''),
            'error': None,
        })

    except json.JSONDecodeError as e:
        return JsonResponse({'status': 'error', 'error': f'JSON inválido: {e}'}, status=400)
    except ImportError as e:
        return JsonResponse({'status': 'error', 'error': f'Error de módulo: {e}'}, status=500)
    except Exception as e:
        logger.error(f"[XAI API] Error inesperado: {e}", exc_info=True)
        return JsonResponse({
            'status': 'error',
            'error': str(e),
            'traceback': traceback.format_exc() if settings.DEBUG else None,
        }, status=500)


@csrf_exempt
@require_http_methods(['POST'])
def predecir_jugador_api(request):
    """
    POST /api/predecir_jugador/
    Body: {jugador_id, jornada, posicion?, modelo?}
    Tries BD prediction → historical mean for early rounds → 404 otherwise.
    """
    try:
        data = json.loads(request.body.decode('utf-8') if isinstance(request.body, bytes) else request.body)
        jugador_id = data.get('jugador_id')
        jornada_num = data.get('jornada')
        posicion_param = data.get('posicion')
        modelo_tipo = data.get('modelo', 'RF')

        if not jugador_id or not jornada_num:
            return JsonResponse({'status': 'error', 'error': 'Se requieren jugador_id y jornada'}, status=400)

        try:
            jugador = Jugador.objects.get(id=jugador_id)
        except Jugador.DoesNotExist:
            return JsonResponse({'status': 'error', 'error': 'Jugador no encontrado'}, status=404)

        temporada_actual = Temporada.objects.last()
        if not temporada_actual:
            return JsonResponse({'status': 'error', 'error': 'Temporada no encontrada'}, status=500)

        jornada = Jornada.objects.filter(numero_jornada=jornada_num, temporada=temporada_actual).first()
        if not jornada:
            return JsonResponse({'status': 'error', 'error': f'Jornada {jornada_num} no encontrada en la temporada actual'}, status=404)

        nombre_jugador = f"{jugador.nombre} {jugador.apellido}".strip()

        prediccion_obj = PrediccionJugador.objects.filter(
            jugador=jugador, jornada=jornada, modelo=modelo_tipo.lower()
        ).first()

        if prediccion_obj:
            return JsonResponse({
                'status': 'success', 'type': 'prediccion',
                'jugador_id': jugador_id, 'jugador_nombre': nombre_jugador,
                'prediccion': round(float(prediccion_obj.prediccion), 2),
                'jornada': jornada_num,
                'posicion': posicion_param or jugador.get_posicion_mas_frecuente() or 'Desconocida',
                'modelo': modelo_tipo, 'fuente': 'prediccion_bd',
            })

        if jornada_num <= 5:
            media_puntos = (
                jugador.estadisticas_partidos.aggregate(media=Avg('puntos_fantasy'))['media'] or 0.0
            )
            return JsonResponse({
                'status': 'success', 'type': 'media',
                'jugador_id': jugador_id, 'jugador_nombre': nombre_jugador,
                'prediccion': round(float(media_puntos), 2),
                'jornada': jornada_num,
                'posicion': posicion_param or jugador.get_posicion_mas_frecuente() or 'Desconocida',
                'modelo': 'Media Histórica', 'fuente': 'media_historica',
                'aviso': f'Jornada {jornada_num}: Sin datos suficientes para predicción. Mostrando media histórica.',
            })

        return JsonResponse({
            'status': 'error',
            'error': f'No hay predicción para jornada {jornada_num} y es demasiado tarde para media',
            'jugador_id': jugador_id, 'jornada': jornada_num,
        }, status=404)

    except json.JSONDecodeError:
        return JsonResponse({'status': 'error', 'error': 'JSON inválido'}, status=400)
    except Exception as e:
        logger.error(f"Error en predecir_jugador_api: {e}", exc_info=True)
        return JsonResponse({'status': 'error', 'error': str(e)}, status=500)
