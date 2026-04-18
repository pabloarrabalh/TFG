import sys
import traceback
from pathlib import Path

from django.db.models import Avg, Count, Sum
from django.conf import settings
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from rest_framework import status

from ..models import *

_ENTRENAMIENTOS_PATH = Path(__file__).parent.parent / 'entrenamientoModelos'


def _ensure_path():
    if str(_ENTRENAMIENTOS_PATH) not in sys.path:
        sys.path.insert(0, str(_ENTRENAMIENTOS_PATH))


class PredecirPorteroView(APIView):
    """POST /api/predecir-portero/"""
    permission_classes = [AllowAny]

    def post(self, request):
        try:
            data = request.data
            jugador_id = data.get('jugador_id')
            jornada = data.get('jornada', None)
            modelo_tipo = data.get('modelo', 'RF')

            if not jugador_id:
                return Response(
                    {'status': 'error', 'error': 'jugador_id es requerido'},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            try:
                jugador = Jugador.objects.get(id=jugador_id)
            except Jugador.DoesNotExist:
                return Response(
                    {'status': 'error', 'error': f'Jugador con ID {jugador_id} no encontrado'},
                    status=status.HTTP_404_NOT_FOUND,
                )

            nombre_jugador = f"{jugador.nombre} {jugador.apellido}".strip()
            _ensure_path()
            from predecir import predecir_puntos_portero  # noqa: PLC0415 – depends on _ensure_path

            resultado = predecir_puntos_portero(nombre_jugador, jornada, verbose=False, modelo_tipo=modelo_tipo)

            if not isinstance(resultado, dict):
                return Response(
                    {'status': 'error', 'error': f'Resultado inválido: {resultado}'},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )

            if resultado.get('error'):
                return Response(
                    {'status': 'error', 'error': resultado['error'], 'jugador_id': jugador_id},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            prediccion = resultado.get('prediccion')
            return Response({
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

        except ImportError as e:
            return Response(
                {'status': 'error', 'error': f'Error de módulo: {e}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
        except Exception as e:
            return Response({
                'status': 'error',
                'error': str(e),
                'traceback': traceback.format_exc() if settings.DEBUG else None,
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class CambiarJornadaLegacyView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        try:
            data = request.data
            nueva_jornada = data.get('jornada')

            if not nueva_jornada or not isinstance(nueva_jornada, int):
                return Response(
                    {'status': 'error', 'error': 'jornada debe ser un entero'},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            temporada_actual = Temporada.objects.last()
            if not temporada_actual:
                return Response(
                    {'status': 'error', 'error': 'No hay temporada disponible'},
                    status=status.HTTP_404_NOT_FOUND,
                )

            jornada_actual = Jornada.objects.filter(
                temporada=temporada_actual, numero_jornada=nueva_jornada
            ).first()
            if not jornada_actual:
                return Response(
                    {'status': 'error', 'error': f'Jornada {nueva_jornada} no existe'},
                    status=status.HTTP_404_NOT_FOUND,
                )

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

            _min_sum: dict = {}
            for _row in (
                EstadisticasPartidoJugador.objects
                .filter(partido__jornada__temporada=temporada_actual)
                .values('jugador_id', 'min_partido')
                .order_by('jugador_id', '-partido__jornada__numero_jornada')
            ):
                _jid = _row['jugador_id']
                if _jid not in _min_sum:
                    _min_sum[_jid] = []
                if len(_min_sum[_jid]) < 4:
                    _min_sum[_jid].append(_row['min_partido'] or 0)
            pocos_minutos_set = {
                jid for jid, mins in _min_sum.items()
                if mins and sum(mins) < 60
            }

            seen_jugadores = set()
            for ejt in EquipoJugadorTemporada.objects.filter(
                temporada=temporada_actual
            ).select_related('jugador', 'equipo').order_by('jugador__nombre'):
                jugador = ejt.jugador
                if jugador.id in seen_jugadores:
                    continue
                seen_jugadores.add(jugador.id)
                posicion = ejt.posicion or 'Delantero'

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
                        'pocos_minutos': jugador.id in pocos_minutos_set,
                    })

            return Response({
                'status': 'success',
                'jornada': nueva_jornada,
                'jugadores_por_posicion': jugadores_por_posicion,
            })

        except Exception as e:
            return Response({'status': 'error', 'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class ExplicarPrediccionView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        try:
            data = request.data
            jugador_id = data.get('jugador_id')
            jornada = data.get('jornada', None)
            posicion_raw = data.get('posicion', None)
            modelo_tipo = data.get('modelo', None)

            if not jugador_id:
                return Response(
                    {'status': 'error', 'error': 'jugador_id es requerido'},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            try:
                jugador = Jugador.objects.get(id=jugador_id)
                nombre_jugador = f"{jugador.nombre} {jugador.apellido}".strip()
            except Jugador.DoesNotExist:
                return Response(
                    {'status': 'error', 'error': f'Jugador {jugador_id} no encontrado'},
                    status=status.HTTP_404_NOT_FOUND,
                )

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
            from predecir import predecir_puntos  # noqa: PLC0415 – depends on _ensure_path

            jornada_para_pred = int(jornada) if jornada is not None else None
            resultado = predecir_puntos(jugador_id, posicion_code, jornada_para_pred, verbose=False, modelo_tipo=modelo_tipo)

            prediccion = resultado.get('prediccion')

            # Guardar predicción en BD para sincronizar con el menú de destacados
            if prediccion is not None and jornada is not None:
                try:
                    _MODEL_MAP = {
                        'RF': 'rf', 'RANDOM FOREST': 'rf',
                        'XGB': 'xgb', 'XGBOOST': 'xgb',
                        'LGBM': 'lgbm',
                        'RIDGE': 'ridge', 'RIDGE REGRESSION': 'ridge',
                        'ELASTICNET': 'elasticnet',
                        'ELASTIC NET': 'elasticnet',
                        'BASELINE': 'baseline',
                    }
                    _POS_DEFAULT = {'PT': 'rf', 'DF': 'rf', 'MC': 'ridge', 'DT': 'ridge'}
                    if modelo_tipo:
                        modelo_bd = _MODEL_MAP.get(str(modelo_tipo).upper(), 'rf')
                    else:
                        modelo_bd = _POS_DEFAULT.get(posicion_code, 'rf')
                    temporada_actual = Temporada.objects.order_by('-nombre').first()
                    if temporada_actual:
                        try:
                            jornada_num = int(jornada)
                            jornada_obj = Jornada.objects.filter(
                                numero_jornada=jornada_num, temporada=temporada_actual
                            ).first()
                            if jornada_obj:
                                PrediccionJugador.objects.update_or_create(
                                    jugador=jugador, jornada=jornada_obj, modelo=modelo_bd,
                                    defaults={'prediccion': float(prediccion)}
                                )
                        except (ValueError, TypeError):
                            pass
                except Exception as e_save:
                    pass

            return Response(resultado, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({
                'status': 'error',
                'error': str(e),
                'traceback': traceback.format_exc() if settings.DEBUG else None,
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class PredecirJugadorView(APIView):
    """POST /api/predecir-jugador/"""
    permission_classes = [AllowAny]

    def post(self, request):
        try:
            data = request.data
            jugador_id = data.get('jugador_id')
            jornada_num = data.get('jornada')
            posicion_param = data.get('posicion')
            modelo_tipo = data.get('modelo', 'RF')

            if not jugador_id or not jornada_num:
                return Response(
                    {'status': 'error', 'error': 'Se requieren jugador_id y jornada'},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            try:
                jugador = Jugador.objects.get(id=jugador_id)
            except Jugador.DoesNotExist:
                return Response({'status': 'error', 'error': 'Jugador no encontrado'}, status=status.HTTP_404_NOT_FOUND)

            temporada_actual = Temporada.objects.last()
            if not temporada_actual:
                return Response({'status': 'error', 'error': 'Temporada no encontrada'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

            jornada = Jornada.objects.filter(numero_jornada=jornada_num, temporada=temporada_actual).first()
            if not jornada:
                return Response(
                    {'status': 'error', 'error': f'Jornada {jornada_num} no encontrada en la temporada actual'},
                    status=status.HTTP_404_NOT_FOUND,
                )

            nombre_jugador = f"{jugador.nombre} {jugador.apellido}".strip()

            prediccion_obj = PrediccionJugador.objects.filter(
                jugador=jugador, jornada=jornada, modelo=modelo_tipo.lower()
            ).first()

            if prediccion_obj:
                return Response({
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
                return Response({
                    'status': 'success', 'type': 'media',
                    'jugador_id': jugador_id, 'jugador_nombre': nombre_jugador,
                    'prediccion': round(float(media_puntos), 2),
                    'jornada': jornada_num,
                    'posicion': posicion_param or jugador.get_posicion_mas_frecuente() or 'Desconocida',
                    'modelo': 'Media Histórica', 'fuente': 'media_historica',
                    'aviso': f'Jornada {jornada_num}: Sin datos suficientes para predicción. Mostrando media histórica.',
                })

            return Response({
                'status': 'error',
                'error': f'No hay predicción para jornada {jornada_num} y es demasiado tarde para media',
                'jugador_id': jugador_id, 'jornada': jornada_num,
            }, status=status.HTTP_404_NOT_FOUND)

        except Exception as e:
            return Response({'status': 'error', 'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
